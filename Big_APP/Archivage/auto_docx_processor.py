import os
import io
import time
import logging
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from app import process_word_document

# Configuration du logging
logging.basicConfig(
    filename=f'logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Les scopes nécessaires pour l'API Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_google_drive_service():
    """
    Authentifie et retourne le service Google Drive.
    """
    creds = None
    
    # Vérifier si token.json existe
    if os.path.exists('token.json'):
        logging.info("Token.json trouvé, tentative de chargement des credentials")
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Si les credentials ne sont pas valides ou n'existent pas
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refresh du token nécessaire")
            creds.refresh(Request())
        else:
            logging.info("Nouvelle authentification nécessaire")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Sauvegarder les credentials pour la prochaine utilisation
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        logging.info("Nouveaux credentials sauvegardés")
    
    # Afficher l'email du compte connecté
    service = build('drive', 'v3', credentials=creds)
    about = service.about().get(fields="user").execute()
    user_email = about['user']['emailAddress']
    logging.info(f"Connecté au compte Google Drive: {user_email}")
    
    return service

def find_folder_id_by_name(service, folder_name):
    """
    Trouve l'ID d'un dossier Google Drive par son nom.
    """
    try:
        logging.info(f"Recherche du dossier: {folder_name}")
        results = service.files().list(
            q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false",
            fields="files(id, name)"
        ).execute()
        
        items = results.get('files', [])
        if items:
            logging.info(f"Dossier {folder_name} trouvé avec l'ID: {items[0]['id']}")
            return items[0]['id']
        logging.warning(f"Dossier {folder_name} non trouvé")
        return None
    except Exception as e:
        logging.error(f"Erreur lors de la recherche du dossier {folder_name}: {str(e)}")
        return None

def download_file(service, file_id):
    """
    Télécharge un fichier depuis Google Drive en mémoire.
    """
    try:
        request = service.files().get_media(fileId=file_id)
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        file.seek(0)
        return file
    except Exception as e:
        logging.error(f"Erreur lors du téléchargement du fichier {file_id}: {str(e)}")
        return None

def upload_file(service, file_content, file_name, folder_id):
    """
    Upload un fichier vers Google Drive dans le dossier spécifié.
    """
    try:
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        media = MediaIoBaseUpload(
            file_content,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            resumable=True
        )
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        return file.get('id')
    except Exception as e:
        logging.error(f"Erreur lors de l'upload du fichier {file_name}: {str(e)}")
        return None

def move_file(service, file_id, destination_folder_id):
    """
    Déplace un fichier vers un autre dossier dans Google Drive.
    """
    try:
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        
        file = service.files().update(
            fileId=file_id,
            addParents=destination_folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        return True
    except Exception as e:
        logging.error(f"Erreur lors du déplacement du fichier {file_id}: {str(e)}")
        return False

def process_documents():
    """
    Fonction principale qui surveille et traite les documents.
    """
    try:
        service = get_google_drive_service()
        logging.info("Service Google Drive initialisé avec succès")
        
        # Trouver les IDs des dossiers
        inbox_id = find_folder_id_by_name(service, 'INBOX')
        outbox_id = find_folder_id_by_name(service, 'OUTBOX')
        archive_id = find_folder_id_by_name(service, 'ARCHIVE')
        
        if not all([inbox_id, outbox_id, archive_id]):
            logging.error("Impossible de trouver un ou plusieurs dossiers requis")
            logging.error(f"INBOX ID: {inbox_id}")
            logging.error(f"OUTBOX ID: {outbox_id}")
            logging.error(f"ARCHIVE ID: {archive_id}")
            return
        
        # Rechercher les fichiers .docx dans INBOX
        logging.info(f"Recherche des fichiers .docx dans le dossier INBOX (ID: {inbox_id})")
        results = service.files().list(
            q=f"'{inbox_id}' in parents and mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' and trashed=false",
            fields="files(id, name)"
        ).execute()
        
        files = results.get('files', [])
        logging.info(f"Nombre de fichiers trouvés dans INBOX: {len(files)}")
        
        if not files:
            logging.info("Aucun nouveau fichier à traiter")
            return
        
        for file in files:
            try:
                logging.info(f"Traitement du fichier: {file['name']} (ID: {file['id']})")
                
                # Télécharger le fichier
                file_content = download_file(service, file['id'])
                if not file_content:
                    logging.error(f"Échec du téléchargement du fichier {file['name']}")
                    continue
                
                # Traiter le document
                logging.info(f"Début du traitement du document {file['name']}")
                processed_content = process_word_document(file_content)
                if not processed_content:
                    logging.error(f"Échec du traitement du document {file['name']}")
                    continue
                
                # Upload le fichier traité dans OUTBOX
                new_file_name = f"processed_{file['name']}"
                logging.info(f"Upload du fichier traité vers OUTBOX: {new_file_name}")
                upload_file(service, processed_content, new_file_name, outbox_id)
                
                # Déplacer le fichier original vers ARCHIVE
                logging.info(f"Déplacement du fichier original vers ARCHIVE: {file['name']}")
                move_file(service, file['id'], archive_id)
                
                logging.info(f"Fichier {file['name']} traité avec succès")
                
            except Exception as e:
                logging.error(f"Erreur lors du traitement du fichier {file['name']}: {str(e)}")
                continue
    
    except Exception as e:
        logging.error(f"Erreur générale: {str(e)}")

def main():
    """
    Fonction principale qui exécute le processus en boucle.
    """
    logging.info("Démarrage du processus de traitement automatique")
    
    while True:
        try:
            process_documents()
            logging.info("Attente de 5 minutes avant la prochaine vérification")
            time.sleep(300)
        except KeyboardInterrupt:
            logging.info("Arrêt du programme demandé par l'utilisateur")
            break
        except Exception as e:
            logging.error(f"Erreur inattendue: {str(e)}")
            time.sleep(300)  # Attendre 5 minutes même en cas d'erreur

if __name__ == "__main__":
    main() 