#!/usr/bin/env python3
"""
Script de test pour point d'accès S3 AWS
Teste les opérations GET et POST sur un point d'accès S3
"""

import boto3
import json
import sys
import traceback
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError

class S3AccessPointTester:
    def __init__(self, access_point_arn, region='eu-west-1'):
        """
        Initialise le testeur de point d'accès S3
        
        Args:
            access_point_arn (str): ARN du point d'accès S3
            region (str): Région AWS
        """
        self.access_point_arn = access_point_arn
        self.region = region
        self.s3_client = None
        self.s3control_client = None
        self.sts_client = None
        self.test_results = []
        
    def initialize_client(self):
        """Initialise les clients S3 et S3 Control"""
        try:
            print("🔧 Tentative d'initialisation des clients S3...")
            self.s3_client = boto3.client('s3', region_name=self.region)
            self.s3control_client = boto3.client('s3control', region_name=self.region)
            self.sts_client = boto3.client('sts', region_name=self.region)
            print(f"✅ Clients S3, S3 Control et STS initialisés pour la région {self.region}")
            return True
        except NoCredentialsError:
            print("❌ Erreur: Credentials AWS non trouvées")
            print("Configurez vos credentials avec 'aws configure' ou via les variables d'environnement")
            return False
        except Exception as e:
            print(f"❌ Erreur lors de l'initialisation des clients S3: {e}")
            print(f"Détails de l'erreur: {traceback.format_exc()}")
            return False
    
    def test_credentials(self):
        """Teste les credentials et affiche les informations de l'utilisateur"""
        print("\n🔐 Test des credentials AWS...")
        try:
            response = self.sts_client.get_caller_identity()
            print(f"✅ Credentials valides")
            print(f"   User ID: {response.get('UserId', 'N/A')}")
            print(f"   Account: {response.get('Account', 'N/A')}")
            print(f"   ARN: {response.get('Arn', 'N/A')}")
            self.test_results.append(("Credentials AWS", "PASS"))
            return True
        except Exception as e:
            print(f"❌ Erreur lors de la vérification des credentials: {e}")
            self.test_results.append(("Credentials AWS", "FAIL"))
            return False
    
    def test_s3control_permissions(self):
        """Teste les permissions S3 Control de base"""
        print("\n🔑 Test des permissions S3 Control...")
        try:
            # Test de list_access_points pour voir si on a les permissions de base
            response = self.s3control_client.list_access_points(
                AccountId=self.access_point_arn.split(':')[4]
            )
            print(f"✅ Permissions S3 Control OK - {len(response.get('AccessPointList', []))} points d'accès trouvés")
            self.test_results.append(("Permissions S3 Control", "PASS"))
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ Erreur S3 Control: {error_code}")
            print(f"   Message: {e.response['Error'].get('Message', 'N/A')}")
            print("   💡 Conseil: Vérifiez que votre utilisateur a les permissions s3:ListAccessPoints")
            self.test_results.append(("Permissions S3 Control", "FAIL"))
            return False
        except Exception as e:
            print(f"❌ Erreur inattendue S3 Control: {e}")
            self.test_results.append(("Permissions S3 Control", "FAIL"))
            return False
    
    def test_access_point_exists(self):
        """Teste si le point d'accès existe et est accessible"""
        print("\n🔍 Test d'existence du point d'accès...")
        try:
            # Extraire le nom du point d'accès de l'ARN
            access_point_name = self.access_point_arn.split('/')[-1]
            account_id = self.access_point_arn.split(':')[4]
            
            print(f"   Nom du point d'accès: {access_point_name}")
            print(f"   ID du compte: {account_id}")
            
            response = self.s3control_client.get_access_point(
                Name=access_point_name,
                AccountId=account_id
            )
            print(f"✅ Point d'accès trouvé: {response['Name']}")
            print(f"   Statut: {response.get('NetworkOrigin', 'N/A')}")
            print(f"   Bucket: {response.get('Bucket', 'N/A')}")
            print(f"   ARN: {response.get('AccessPointArn', 'N/A')}")
            self.test_results.append(("Existence du point d'accès", "PASS"))
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ Erreur lors de la vérification du point d'accès: {error_code}")
            print(f"   Message: {e.response['Error'].get('Message', 'N/A')}")
            
            if error_code == 'AccessDenied':
                print("   💡 Conseils pour résoudre AccessDenied:")
                print("      - Vérifiez que votre utilisateur a les permissions s3:GetAccessPoint")
                print("      - Vérifiez que vous êtes dans le bon compte AWS")
                print("      - Vérifiez que le point d'accès existe dans cette région")
                print("      - Vérifiez les politiques IAM attachées à votre utilisateur")
            
            self.test_results.append(("Existence du point d'accès", "FAIL"))
            return False
        except Exception as e:
            print(f"❌ Erreur inattendue: {e}")
            print(f"Détails: {traceback.format_exc()}")
            self.test_results.append(("Existence du point d'accès", "FAIL"))
            return False
    
    def test_list_objects(self):
        """Teste l'opération GET (list objects)"""
        print("\n📋 Test GET - Liste des objets...")
        try:
            # Utiliser l'ARN du point d'accès comme nom de bucket
            print(f"   Utilisation de l'ARN comme bucket: {self.access_point_arn}")
            response = self.s3_client.list_objects_v2(
                Bucket=self.access_point_arn,
                MaxKeys=10
            )
            
            object_count = response.get('KeyCount', 0)
            print(f"✅ GET réussi - {object_count} objets trouvés")
            
            if object_count > 0:
                print("   Premiers objets:")
                for obj in response.get('Contents', [])[:5]:
                    print(f"   - {obj['Key']} ({obj['Size']} bytes)")
            
            self.test_results.append(("GET - List Objects", "PASS"))
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ Erreur GET: {error_code}")
            print(f"   Message: {e.response['Error'].get('Message', 'N/A')}")
            self.test_results.append(("GET - List Objects", "FAIL"))
            return False
        except Exception as e:
            print(f"❌ Erreur inattendue lors du GET: {e}")
            print(f"Détails: {traceback.format_exc()}")
            self.test_results.append(("GET - List Objects", "FAIL"))
            return False
    
    def test_put_object(self):
        """Teste l'opération POST/PUT (upload d'un fichier de test)"""
        print("\n📤 Test PUT - Upload d'un objet de test...")
        
        test_key = f"test-access-point-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        test_content = f"Test file created at {datetime.now().isoformat()}\nAccess Point: {self.access_point_arn}"
        
        try:
            print(f"   Upload de l'objet: {test_key}")
            response = self.s3_client.put_object(
                Bucket=self.access_point_arn,
                Key=test_key,
                Body=test_content.encode('utf-8'),
                ContentType='text/plain'
            )
            
            print(f"✅ PUT réussi - Objet uploadé: {test_key}")
            print(f"   ETag: {response.get('ETag', 'N/A')}")
            self.test_results.append(("PUT - Upload Object", "PASS"))
            
            # Test de lecture du fichier uploadé
            return self.test_get_object(test_key)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ Erreur PUT: {error_code}")
            print(f"   Message: {e.response['Error'].get('Message', 'N/A')}")
            self.test_results.append(("PUT - Upload Object", "FAIL"))
            return False
        except Exception as e:
            print(f"❌ Erreur inattendue lors du PUT: {e}")
            print(f"Détails: {traceback.format_exc()}")
            self.test_results.append(("PUT - Upload Object", "FAIL"))
            return False
    
    def test_get_object(self, key):
        """Teste la lecture d'un objet spécifique"""
        print(f"\n📥 Test GET - Lecture de l'objet {key}...")
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.access_point_arn,
                Key=key
            )
            
            content = response['Body'].read().decode('utf-8')
            print(f"✅ GET objet réussi")
            print(f"   Taille: {len(content)} caractères")
            print(f"   Contenu: {content[:100]}{'...' if len(content) > 100 else ''}")
            
            self.test_results.append(("GET - Read Object", "PASS"))
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ Erreur GET objet: {error_code}")
            print(f"   Message: {e.response['Error'].get('Message', 'N/A')}")
            self.test_results.append(("GET - Read Object", "FAIL"))
            return False
        except Exception as e:
            print(f"❌ Erreur inattendue lors du GET objet: {e}")
            print(f"Détails: {traceback.format_exc()}")
            self.test_results.append(("GET - Read Object", "FAIL"))
            return False
    
    def test_delete_object(self, key):
        """Nettoie en supprimant l'objet de test"""
        print(f"\n🗑️  Nettoyage - Suppression de l'objet de test...")
        
        try:
            self.s3_client.delete_object(
                Bucket=self.access_point_arn,
                Key=key
            )
            print(f"✅ Objet de test supprimé: {key}")
            return True
        except Exception as e:
            print(f"⚠️  Attention: Impossible de supprimer l'objet de test: {e}")
            return False
    
    def run_all_tests(self):
        """Lance tous les tests"""
        print("🚀 Début des tests du point d'accès S3")
        print(f"Point d'accès: {self.access_point_arn}")
        print("=" * 60)
        
        if not self.initialize_client():
            return False
        
        # Test 0: Vérifier les credentials
        if not self.test_credentials():
            print("\n❌ Impossible de continuer - Credentials invalides")
            return False
        
        # Test 1: Vérifier les permissions S3 Control
        if not self.test_s3control_permissions():
            print("\n⚠️  Permissions S3 Control insuffisantes")
            print("   Le script continuera mais certains tests pourraient échouer")
        
        # Test 2: Vérifier l'existence du point d'accès
        if not self.test_access_point_exists():
            print("\n❌ Impossible de continuer - Point d'accès non accessible")
            print("\n🔧 Actions recommandées:")
            print("   1. Vérifiez que l'ARN du point d'accès est correct")
            print("   2. Vérifiez que vous êtes dans le bon compte AWS")
            print("   3. Vérifiez les permissions IAM de votre utilisateur")
            print("   4. Vérifiez que le point d'accès existe dans la région spécifiée")
            return False
        
        # Test 3: List objects (GET)
        self.test_list_objects()
        
        # Test 4: Upload et lecture d'un objet (PUT/GET)
        test_key = None
        if self.test_put_object():
            test_key = f"test-access-point-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        
        # Nettoyage
        if test_key:
            self.test_delete_object(test_key)
        
        # Résumé des résultats
        self.print_summary()
        
        return all(result[1] == "PASS" for result in self.test_results)
    
    def print_summary(self):
        """Affiche le résumé des tests"""
        print("\n" + "=" * 60)
        print("📊 RÉSUMÉ DES TESTS")
        print("=" * 60)
        
        for test_name, result in self.test_results:
            status_icon = "✅" if result == "PASS" else "❌"
            print(f"{status_icon} {test_name}: {result}")
        
        passed = sum(1 for _, result in self.test_results if result == "PASS")
        total = len(self.test_results)
        
        print(f"\nRésultat global: {passed}/{total} tests réussis")
        
        if passed == total:
            print("🎉 Tous les tests sont passés ! Votre point d'accès fonctionne correctement.")
        else:
            print("⚠️  Certains tests ont échoué. Vérifiez les permissions et la configuration.")


def main():
    """Fonction principale"""
    try:
        print("🔧 Démarrage du script de test S3...")
        
        # Configuration - Remplacez par votre ARN de point d'accès
        ACCESS_POINT_ARN = "arn:aws:s3:eu-west-1:488643426355:accesspoint/accesspoint-megascope"
        REGION = "eu-west-1"  # Région de votre point d'accès
        
        print("🔧 Configuration:")
        print(f"   Point d'accès: {ACCESS_POINT_ARN}")
        print(f"   Région: {REGION}")
        
        # Créer et lancer le testeur
        tester = S3AccessPointTester(ACCESS_POINT_ARN, REGION)
        success = tester.run_all_tests()
        
        # Code de sortie
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Erreur fatale dans le script principal: {e}")
        print(f"Détails: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()