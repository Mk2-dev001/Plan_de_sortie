import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import json
import time
import datetime
import os
from dotenv import load_dotenv
from openai import OpenAI
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from urllib.parse import urlparse, parse_qs
import base64
from io import BytesIO
import re
from functools import lru_cache
import hashlib
import logging
from datetime import timedelta
import sqlite3
from pathlib import Path
from Levenshtein import distance
import sys
import dateutil.parser

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Désactiver les logs verbeux des bibliothèques externes
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Constantes
API_QUOTA_EXCEEDED_ERROR = "quotaExceeded"
API_RETRY_DELAY = 1
API_MAX_RETRIES = 3
CACHE_DURATION = 3600  # 1 heure
CLEANUP_INTERVAL = 300  # 5 minutes

# Log au démarrage de l'application
logger.info("=== DÉMARRAGE DE L'APPLICATION ===")
logger.info(f"Python version: {sys.version}")
logger.info(f"Working directory: {os.getcwd()}")

# Chargement des variables d'environnement
logger.info("Chargement des variables d'environnement...")
env_path = Path('.env')
if not env_path.exists():
    logger.warning("Fichier .env non trouvé. Tentative de chargement depuis les variables d'environnement système.")
else:
    load_dotenv(dotenv_path=env_path)
    logger.info("Fichier .env chargé")

# Vérification des variables d'environnement requises
required_env_vars = {
    "YOUTUBE_API_KEY": "YouTube API",
    "OPENAI_API_KEY": "OpenAI API",
    "INSTAGRAM_RAPID_API_KEY": "Instagram API",
    "INSTAGRAM_RAPID_API_HOST": "Instagram API Host"
}

missing_vars = []
for var, service in required_env_vars.items():
    if not os.getenv(var):
        missing_vars.append(f"{var} ({service})")
        logger.error(f"Variable d'environnement manquante: {var} ({service})")

if missing_vars:
    logger.warning(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")
    logger.warning("Certaines fonctionnalités pourraient ne pas fonctionner correctement.")
else:
    logger.info("Toutes les variables d'environnement requises sont présentes")

# Vérification spécifique pour NEWS_API_KEY
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
if not NEWS_API_KEY:
    logger.warning("NEWS_API_KEY manquante. L'analyse des actualités sera limitée.")
else:
    logger.info("NEWS_API_KEY trouvée")

class APICache:
    """Gestionnaire de cache pour les requêtes API"""
    def __init__(self, cache_duration=CACHE_DURATION):
        self.cache = {}
        self.cache_duration = cache_duration
        self.last_cleanup = time.time()

    def get(self, key):
        """Récupère une valeur du cache"""
        self._cleanup_if_needed()
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_duration:
                logger.debug(f"Cache hit pour {key}")
                return data
            else:
                logger.debug(f"Cache expiré pour {key}")
                del self.cache[key]
        return None

    def set(self, key, value):
        """Stocke une valeur dans le cache"""
        self.cache[key] = (value, time.time())
        logger.debug(f"Cache mis à jour pour {key}")

    def _cleanup_if_needed(self):
        """Nettoie le cache si nécessaire"""
        current_time = time.time()
        if current_time - self.last_cleanup > CLEANUP_INTERVAL:
            self._cleanup()
            self.last_cleanup = current_time

    def _cleanup(self):
        """Nettoie les entrées expirées du cache"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if current_time - timestamp >= self.cache_duration
        ]
        for key in expired_keys:
            del self.cache[key]
        logger.debug(f"Nettoyage du cache: {len(expired_keys)} entrées supprimées")

class APIRequestManager:
    """Gestionnaire de requêtes API avec retry et rate limiting"""
    def __init__(self, max_retries=API_MAX_RETRIES, retry_delay=API_RETRY_DELAY):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_request_time = {}
        self.min_request_interval = 0.1  # 100ms entre les requêtes

    def execute_request(self, platform, request_func, *args, **kwargs):
        """Exécute une requête API avec gestion des erreurs et rate limiting"""
        self._wait_for_rate_limit(platform)
        
        for attempt in range(self.max_retries):
            try:
                result = request_func(*args, **kwargs)
                self.last_request_time[platform] = time.time()
                return result
            except HttpError as e:
                if API_QUOTA_EXCEEDED_ERROR in str(e):
                    logger.error(f"Quota API dépassé pour {platform}")
                    raise
                if attempt == self.max_retries - 1:
                    logger.error(f"Échec final de la requête {platform}: {str(e)}")
                    raise
                delay = self.retry_delay * (2 ** attempt)
                logger.warning(f"Tentative {attempt + 1} échouée pour {platform}: {str(e)}. Nouvelle tentative dans {delay}s")
                time.sleep(delay)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Erreur inattendue pour {platform}: {str(e)}")
                    raise
                delay = self.retry_delay * (2 ** attempt)
                logger.warning(f"Tentative {attempt + 1} échouée pour {platform}: {str(e)}. Nouvelle tentative dans {delay}s")
                time.sleep(delay)

    def _wait_for_rate_limit(self, platform):
        """Attend si nécessaire pour respecter les limites de taux"""
        if platform in self.last_request_time:
            elapsed = time.time() - self.last_request_time[platform]
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)

class APIKeyManager:
    """Gestionnaire de clés API avec mise en cache et gestion des erreurs"""
    
    def __init__(self):
        self.youtube_api_key = None
        self.news_api_key = None
        self.youtube_api_errors = 0
        self.news_api_errors = 0
        self.max_errors = 3  # Nombre maximum d'erreurs avant de désactiver une clé
        self.error_reset_time = 3600  # Temps en secondes avant de réinitialiser les erreurs (1 heure)
        self.last_error_reset = time.time()
        self.cache = {}  # Cache pour les résultats d'API
        self.cache_duration = 3600  # Durée de vie du cache en secondes (1 heure)
        
        # Chargement initial des clés
        self._load_api_keys()
        
    def _load_api_keys(self):
        """Charge les clés API depuis les variables d'environnement"""
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        self.news_api_key = os.getenv("NEWS_API_KEY")
        
        if not self.youtube_api_key:
            logger.warning("Clé YouTube API non trouvée")
        if not self.news_api_key:
            logger.warning("Clé News API non trouvée")
    
    def get_youtube_api_key(self):
        """Récupère la clé YouTube API si elle est disponible"""
        # Vérifier si on doit réinitialiser les erreurs
        self._check_error_reset()
        
        if self.youtube_api_errors >= self.max_errors:
            logger.warning("Clé YouTube API désactivée en raison de trop d'erreurs")
            return None
            
        return self.youtube_api_key
    
    def get_news_api_key(self):
        """Récupère la clé News API si elle est disponible"""
        # Vérifier si on doit réinitialiser les erreurs
        self._check_error_reset()
        
        if self.news_api_errors >= self.max_errors:
            logger.warning("Clé News API désactivée en raison de trop d'erreurs")
            return None
            
        return self.news_api_key
    
    def mark_youtube_api_error(self):
        """Marque une erreur pour la clé YouTube API"""
        self.youtube_api_errors += 1
        logger.warning(f"Erreur YouTube API ({self.youtube_api_errors}/{self.max_errors})")
    
    def mark_news_api_error(self):
        """Marque une erreur pour la clé News API"""
        self.news_api_errors += 1
        logger.warning(f"Erreur News API ({self.news_api_errors}/{self.max_errors})")
    
    def _check_error_reset(self):
        """Vérifie si on doit réinitialiser les compteurs d'erreurs"""
        current_time = time.time()
        if current_time - self.last_error_reset > self.error_reset_time:
            if self.youtube_api_errors > 0 or self.news_api_errors > 0:
                logger.info("Réinitialisation des compteurs d'erreurs API")
            self.youtube_api_errors = 0
            self.news_api_errors = 0
            self.last_error_reset = current_time
    
    def get_cached_result(self, key):
        """Récupère un résultat du cache s'il est valide"""
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_duration:
                logger.debug(f"Résultat trouvé dans le cache pour {key}")
                return result
            else:
                logger.debug(f"Résultat expiré dans le cache pour {key}")
                del self.cache[key]
        return None
    
    def cache_result(self, key, result):
        """Met en cache un résultat"""
        self.cache[key] = (result, time.time())
        logger.debug(f"Résultat mis en cache pour {key}")
    
    def clear_cache(self):
        """Vide le cache"""
        self.cache = {}
        logger.info("Cache vidé")

class CacheManager:
    def __init__(self, cache_duration=3600):  # 1 heure par défaut
        self.cache = {}
        self.cache_duration = cache_duration
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # Nettoyage toutes les 5 minutes

    def get(self, key):
        self._cleanup_if_needed()
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_duration:
                return data
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        self.cache[key] = (value, time.time())

    def _cleanup_if_needed(self):
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup()
            self.last_cleanup = current_time

    def _cleanup(self):
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if current_time - timestamp >= self.cache_duration
        ]
        for key in expired_keys:
            del self.cache[key]

class RetryManager:
    """Gestionnaire de tentatives avec backoff exponentiel"""
    def __init__(self, max_retries=3, base_delay=1):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    def execute_with_retry(self, func, *args, **kwargs):
        """Exécute une fonction avec retry en cas d'échec"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Tentative {attempt + 1} échouée: {str(e)}. Nouvelle tentative dans {delay}s")
                time.sleep(delay)
        
        logger.error(f"Toutes les tentatives ont échoué: {str(last_error)}")
        raise last_error

# Initialisation des gestionnaires globaux
api_manager = APIKeyManager()
cache_manager = CacheManager()
retry_manager = RetryManager()

# Configuration des API keys avec le nouveau gestionnaire
YOUTUBE_API_KEY = api_manager.get_youtube_api_key()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INSTAGRAM_RAPID_API_KEY = os.getenv("INSTAGRAM_RAPID_API_KEY")
INSTAGRAM_RAPID_API_HOST = os.getenv("INSTAGRAM_RAPID_API_HOST")

# Initialisation du client OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialisation de l'API YouTube avec retry
def get_youtube_client():
    """Crée un client YouTube avec la clé API actuelle"""
    return build(
        "youtube", "v3",
        developerKey=api_manager.get_youtube_api_key(),
        cache_discovery=False
    )

youtube = get_youtube_client()

class FallbackData:
    """Classe pour gérer les données de fallback de manière centralisée"""
    YOUTUBE_BENCHMARKS = {
        "poor": 1.0,
        "average": 2.0,
        "good": 4.0,
        "excellent": 6.0
    }

    INSTAGRAM_BENCHMARKS = {
        "poor": 1.0,
        "average": 3.0,
        "good": 5.0,
        "excellent": 7.0
    }

    @staticmethod
    def get_industry_average():
        """Retourne la moyenne d'engagement du secteur"""
        return 3.5  # Valeur moyenne typique pour le secteur

    @staticmethod
    def get_creator_specific_stats(creator_name):
        """Retourne des statistiques spécifiques pour certains créateurs"""
        creators = {
            "squeezie": {
                "short_videos": {
                    "count": 12,
                    "total_views": 36000000,
                    "total_likes": 2160000,
                    "total_comments": 180000,
                    "avg_views": 3000000,
                    "avg_likes": 180000,
                    "avg_comments": 15000,
                    "engagement_rate": 6.5
                },
                "medium_videos": {
                    "count": 15,
                    "total_views": 75000000,
                    "total_likes": 3750000,
                    "total_comments": 300000,
                    "avg_views": 5000000,
                    "avg_likes": 250000,
                    "avg_comments": 20000,
                    "engagement_rate": 5.8
                },
                "long_videos": {
                    "count": 8,
                    "total_views": 32000000,
                    "total_likes": 1920000,
                    "total_comments": 160000,
                    "avg_views": 4000000,
                    "avg_likes": 240000,
                    "avg_comments": 20000,
                    "engagement_rate": 6.2
                }
            },
            "norman": {
                "short_videos": {
                    "count": 8,
                    "total_views": 24000000,
                    "total_likes": 960000,
                    "total_comments": 48000,
                    "avg_views": 3000000,
                    "avg_likes": 120000,
                    "avg_comments": 6000,
                    "engagement_rate": 4.2
                },
                "medium_videos": {
                    "count": 12,
                    "total_views": 48000000,
                    "total_likes": 2400000,
                    "total_comments": 144000,
                    "avg_views": 4000000,
                    "avg_likes": 200000,
                    "avg_comments": 12000,
                    "engagement_rate": 5.3
                },
                "long_videos": {
                    "count": 3,
                    "total_views": 9000000,
                    "total_likes": 450000,
                    "total_comments": 36000,
                    "avg_views": 3000000,
                    "avg_likes": 150000,
                    "avg_comments": 12000,
                    "engagement_rate": 5.4
                }
            }
        }
        return creators.get(creator_name.lower())

    @staticmethod
    def get_generic_stats(platform):
        """Retourne des statistiques génériques pour une plateforme"""
        if platform.lower() == "youtube":
            return {
                "short_videos": {
                    "count": 15,
                    "total_views": 1500000,
                    "total_likes": 75000,
                    "total_comments": 5000,
                    "avg_views": 100000,
                    "avg_likes": 5000,
                    "avg_comments": 333,
                    "engagement_rate": 5.33
                },
                "medium_videos": {
                    "count": 20,
                    "total_views": 2000000,
                    "total_likes": 100000,
                    "total_comments": 8000,
                    "avg_views": 100000,
                    "avg_likes": 5000,
                    "avg_comments": 400,
                    "engagement_rate": 5.4
                },
                "long_videos": {
                    "count": 10,
                    "total_views": 1000000,
                    "total_likes": 50000,
                    "total_comments": 4000,
                    "avg_views": 100000,
                    "avg_likes": 5000,
                    "avg_comments": 400,
                    "engagement_rate": 5.4
                }
            }
        else:  # Instagram
            return {
                "photos": {
                    "count": 30,
                    "total_likes": 150000,
                    "total_comments": 5000,
                    "avg_likes": 5000,
                    "avg_comments": 167,
                    "engagement_rate": 5.17
                },
                "videos": {
                    "count": 15,
                    "total_likes": 90000,
                    "total_comments": 3000,
                    "avg_likes": 6000,
                    "avg_comments": 200,
                    "engagement_rate": 6.2
                },
                "carousels": {
                    "count": 10,
                    "total_likes": 60000,
                    "total_comments": 2000,
                    "avg_likes": 6000,
                    "avg_comments": 200,
                    "engagement_rate": 6.2
                }
            }

class DataManager:
    """Gestionnaire centralisé des données"""
    def __init__(self, use_api=True):
        self.cache = APICache()
        self.request_manager = APIRequestManager()
        self.fallback_data = FallbackData()
        self.use_api = use_api
        self.news_api_key = os.getenv("NEWS_API_KEY")
        
    def get_platform_data(self, username, platform):
        """Récupère les données d'une plateforme avec gestion du cache"""
        if not username:
            logger.error("Nom d'utilisateur non fourni")
            return None
            
        cache_key = f"{platform}_{username}_{'api' if self.use_api else 'demo'}"
        cached_data = self.cache.get(cache_key)
        
        if cached_data:
            logger.info(f"Données récupérées du cache pour {username} sur {platform}")
            return cached_data
            
        try:
            if platform.lower() == "youtube":
                data = self._fetch_youtube_data(username)
            else:
                data = self._fetch_instagram_data(username)
                
            if data:
                self.cache.set(cache_key, data)
                logger.info(f"Données mises en cache pour {username} sur {platform}")
                return data
                
        except HttpError as e:
            if API_QUOTA_EXCEEDED_ERROR in str(e):
                logger.error(f"Quota API dépassé pour {platform}")
                if not self.use_api:
                    return self._get_fallback_data(platform)
                return None
            logger.error(f"Erreur HTTP lors de la récupération des données {platform}: {str(e)}")
            if not self.use_api:
                return self._get_fallback_data(platform)
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données {platform}: {str(e)}")
            if not self.use_api:
                return self._get_fallback_data(platform)
            return None
            
    def _get_fallback_data(self, platform):
        """Récupère les données de fallback pour une plateforme"""
        stats = self.fallback_data.get_generic_stats(platform)
        return {
            "platform_data": {},
            "engagement_metrics": {},
            "reputation_data": {},
            "video_stats": stats if platform.lower() == "youtube" else {},
            "post_stats": stats if platform.lower() == "instagram" else {}
        }
            
    def _fetch_youtube_data(self, username):
        """Récupère les données YouTube brutes"""
        channel_id = self._get_youtube_channel_id(username)
        if not channel_id:
            logger.error(f"ID de chaîne YouTube non trouvé pour {username}")
            return None
        
        if self.use_api:
            try:
                stats = self.request_manager.execute_request(
                    "youtube",
                    lambda: self._get_youtube_stats_api(channel_id)
                )
            except HttpError as e:
                if API_QUOTA_EXCEEDED_ERROR in str(e):
                    logger.error("Quota YouTube API dépassé")
                    raise
                logger.error(f"Erreur lors de la récupération des stats YouTube: {str(e)}")
                return None
        else:
            stats = self._get_youtube_stats_demo(username)
        
        if not stats:
            return None
        
        return {
            "platform_data": stats,
            "engagement_metrics": self._calculate_engagement(stats),
            "reputation_data": self._analyze_reputation(username),
            "video_stats": self._analyze_video_stats(channel_id)
        }
        
    def _fetch_instagram_data(self, username):
        """Récupère les données Instagram brutes"""
        if self.use_api:
            stats = self.request_manager.execute_request(
                "instagram",
                lambda: self._get_instagram_stats_api(username)
            )
        else:
            stats = self._get_instagram_stats_demo(username)
        
        if not stats:
            return None
        
        return {
            "platform_data": stats,
            "engagement_metrics": self._calculate_engagement(stats),
            "reputation_data": self._analyze_reputation(username),
            "post_stats": self._analyze_post_stats(username)
        }
        
    def _calculate_engagement(self, stats):
        """Calcule les métriques d'engagement"""
        try:
            views = int(stats.get("viewCount", 0))
            subscribers = int(stats.get("subscriberCount", 0))
            likes = int(stats.get("likeCount", 0))
            if self.use_api:
                # En mode API, on ne calcule le taux d'engagement que si on a des likes
                if subscribers == 0 or likes == 0:
                    return {"overall_engagement_rate": 0, "benchmark": "unknown", "industry_average": self.fallback_data.get_industry_average()}
            else:
                if subscribers == 0:
                    return {"overall_engagement_rate": 0, "benchmark": "unknown", "industry_average": self.fallback_data.get_industry_average()}
            engagement_rate = (likes / subscribers) * 100 if subscribers else 0
            benchmark = self._get_engagement_benchmark(engagement_rate)
            return {
                "overall_engagement_rate": engagement_rate,
                "benchmark": benchmark,
                "industry_average": self.fallback_data.get_industry_average()
            }
        except Exception as e:
            logger.error(f"Erreur lors du calcul de l'engagement: {str(e)}")
            return {"overall_engagement_rate": 0, "benchmark": "unknown", "industry_average": self.fallback_data.get_industry_average()}
        
    def _get_engagement_benchmark(self, rate):
        if rate >= 10:
            return "excellent"
        elif rate >= 5:
            return "good"
        elif rate >= 2:
            return "average"
        elif rate >= 1:
            return "poor"
        else:
            return "below_average"
        
    def _analyze_sentiment(self, text):
        """Analyse le sentiment d'un texte avec OpenAI"""
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Tu es un expert en analyse de sentiment. Réponds uniquement avec un score entre -1 (très négatif) et 1 (très positif)."},
                    {"role": "user", "content": f"Analyse le sentiment de ce texte et donne un score entre -1 et 1: {text}"}
                ],
                temperature=0,
                max_tokens=10
            )
            try:
                sentiment_score = float(response.choices[0].message.content.strip())
                return max(-1, min(1, sentiment_score))  # Assure que le score est entre -1 et 1
            except ValueError:
                logger.error("Impossible de convertir la réponse OpenAI en score")
                return 0
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de sentiment: {str(e)}")
            return 0

    def _analyze_reputation(self, username):
        """Analyse la réputation du créateur (API ou démo)"""
        # Mots-clés étendus pour la détection des polémiques
        CONTROVERSY_KEYWORDS = {
            "polémique": -0.4,  # Réduit l'impact des mots-clés
            "scandale": -0.5,
            "controverse": -0.3,
            "bad buzz": -0.3,
            "accusé": -0.3,
            "racisme": -0.8,  # Garde un impact fort pour les sujets graves
            "harcèlement": -0.8,
            "agression": -0.8,
            "plainte": -0.3,
            "procès": -0.3,
            "critique": -0.2,
            "clash": -0.2,
            "drama": -0.2,
            "fake": -0.3,
            "mensonge": -0.3,
            "tricherie": -0.4,
            "boycott": -0.3,
            "fraude": -0.5,
            "manipulation": -0.4,
            "malversation": -0.5
        }

        try:
            # Construire l'URL de recherche Google News avec des guillemets pour la recherche exacte
            # et en excluant les termes non pertinents
            search_query = f'"{username}" (youtube OR influenceur OR créateur) -anime -manga -japonais -japon'
            encoded_query = requests.utils.quote(search_query)
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=fr&gl=FR&ceid=FR:fr"
            
            logger.info(f"Tentative d'appel à Google News RSS pour {username}")
            response = requests.get(url)
            logger.info(f"Réponse Google News RSS reçue avec status code: {response.status_code}")
            
            if response.status_code == 200:
                # Parser le XML
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.content)
                
                # Extraire les articles
                articles = []
                for item in root.findall('.//item'):
                    title = item.find('title').text
                    description = item.find('description').text
                    
                    # Vérifier si l'article est vraiment pertinent
                    if username.lower() not in title.lower() and username.lower() not in description.lower():
                        continue
                        
                    article = {
                        "title": title,
                        "description": description,
                        "url": item.find('link').text,
                        "date": item.find('pubDate').text,
                        "source": "Google News"
                    }
                    articles.append(article)
                
                logger.info(f"Nombre d'articles trouvés pour {username}: {len(articles)}")
                
                # Si aucun article pertinent n'est trouvé
                if not articles:
                    return {
                        "score": "Non disponible",
                        "risk_level": "unknown",
                        "status": "no_data",
                        "summary": f"Aucun article mentionnant {username} trouvé.",
                        "controversies": [],
                        "all_articles": [],
                        "metrics": {
                            "average_sentiment": 0,
                            "controversy_score": 0,
                            "articles_analyzed": 0
                        }
                    }
                
                # Initialisation des variables d'analyse
                controversies = []
                all_articles = []
                total_sentiment = 0
                weighted_controversy_score = 0
                articles_analyzed = 0
                
                for article in articles:
                    title = article["title"].lower()
                    description = article["description"].lower()
                    full_text = f"{title} {description}"
                    
                    # Analyse du sentiment
                    sentiment = self._analyze_sentiment(full_text)
                    total_sentiment += sentiment
                    articles_analyzed += 1
                    
                    # Détection des mots-clés de controverse
                    article_controversy_score = 0
                    found_keywords = []
                    
                    for keyword, impact in CONTROVERSY_KEYWORDS.items():
                        if keyword in title or keyword in description:
                            article_controversy_score += impact
                            found_keywords.append(keyword)
                    
                    # Préparation des données de l'article
                    article_data = {
                        "title": article["title"],
                        "url": article["url"],
                        "date": article["date"],
                        "source": article["source"],
                        "sentiment": sentiment,
                        "controversy_score": article_controversy_score
                    }
                    
                    if found_keywords:
                        article_data["keywords"] = found_keywords
                        controversies.append(article_data)
                        weighted_controversy_score += article_controversy_score
                    
                    all_articles.append(article_data)
                
                # Calcul des scores finaux
                avg_sentiment = total_sentiment / articles_analyzed if articles_analyzed > 0 else 0
                reputation_score = int((avg_sentiment + 1) * 50)  # Convertit [-1,1] en [0,100]
                
                # Ajustement du score en fonction des controverses (moins punitif)
                if weighted_controversy_score < 0:
                    reputation_score = max(0, reputation_score + int(weighted_controversy_score * 5))  # Réduit l'impact des controverses
                
                # Détermination du niveau de risque avec des seuils plus cléments
                if reputation_score >= 80:
                    risk_level = "excellent"
                elif reputation_score >= 60:
                    risk_level = "bon"
                elif reputation_score >= 40:
                    risk_level = "moyen"
                elif reputation_score >= 20:
                    risk_level = "à surveiller"
                else:
                    risk_level = "risqué"
                
                # Préparation du résumé
                if controversies:
                    summary = f"{len(controversies)} polémique(s) détectée(s) dans la presse sur {articles_analyzed} articles analysés."
                    logger.warning(f"Polémiques détectées pour {username}: {len(controversies)}")
                else:
                    summary = f"Aucune polémique détectée sur {articles_analyzed} articles analysés."
                
                return {
                    "score": reputation_score,
                    "risk_level": risk_level,
                    "status": "positive" if reputation_score >= 60 else "negative",
                    "summary": summary,
                    "controversies": controversies,
                    "all_articles": all_articles,
                    "metrics": {
                        "average_sentiment": avg_sentiment,
                        "controversy_score": weighted_controversy_score,
                        "articles_analyzed": articles_analyzed
                    }
                }
                
            else:
                error_msg = f"Erreur Google News RSS: {response.status_code}"
                logger.error(error_msg)
                return {
                    "score": "Non disponible",
                    "risk_level": "unknown",
                    "status": "error",
                    "summary": f"Aucune donnée de réputation disponible ({error_msg})",
                    "controversies": [],
                    "all_articles": [],
                    "metrics": {}
                }
                
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de réputation: {str(e)}", exc_info=True)
            return {
                "score": "Non disponible",
                "risk_level": "unknown",
                "status": "error",
                "summary": "Aucune donnée de réputation disponible (erreur lors de l'analyse)",
                "controversies": [],
                "all_articles": [],
                "metrics": {}
            }
    
    def _analyze_video_stats(self, channel_id, period_months=None):
        """Analyse les statistiques des vidéos YouTube avec une gestion améliorée de la pagination et des catégories
        
        Args:
            channel_id (str): L'ID de la chaîne YouTube
            period_months (int, optional): Nombre de mois à analyser. None pour toutes les vidéos.
            
        Returns:
            dict: Statistiques détaillées par catégorie
        """
        if not self.use_api:
            # Mode démo - retourne des données simulées
            return {
                "gaming": {
                    "count": 15,
                    "total_views": 7500000,
                    "total_likes": 375000,
                    "total_comments": 15000,
                    "avg_views": 500000,
                    "avg_likes": 25000,
                    "avg_comments": 1000,
                    "engagement_rate": 5.0
                },
                "vlog": {
                    "count": 10,
                    "total_views": 3000000,
                    "total_likes": 150000,
                    "total_comments": 5000,
                    "avg_views": 300000,
                    "avg_likes": 15000,
                    "avg_comments": 500,
                    "engagement_rate": 5.0
                },
                "autre": {
                    "count": 5,
                    "total_views": 1000000,
                    "total_likes": 50000,
                    "total_comments": 1500,
                    "avg_views": 200000,
                    "avg_likes": 10000,
                    "avg_comments": 300,
                    "engagement_rate": 5.0
                },
                "Total": {
                    "count": 30,
                    "total_views": 11500000,
                    "total_likes": 575000,
                    "total_comments": 21500,
                    "avg_views": 383333,
                    "avg_likes": 19166,
                    "avg_comments": 716,
                    "engagement_rate": 5.0
                }
            }

        try:
            youtube = get_youtube_client()
            video_ids = []
            video_info = []
            nextPageToken = None
            now = datetime.datetime.now(datetime.timezone.utc)
            cutoff = None
            
            if period_months:
                cutoff = now - datetime.timedelta(days=30*period_months)
                logger.info(f"Filtrage des vidéos depuis {cutoff.strftime('%Y-%m-%d %H:%M:%S %Z')}")

            # Configuration des catégories avec des mots-clés plus précis
            categories = {
                "gaming": ["gaming", "jeu", "game", "minecraft", "fortnite", "gta", "call of duty", "fifa", "valorant", "league of legends", "csgo", "stream", "live", "twitch"],
                "vlog": ["vlog", "daily", "journee", "routine", "voyage", "travel", "ma vie", "mon quotidien", "day in my life", "dans ma vie"],
                "music": ["music", "musique", "clip", "cover", "chanson", "song", "feat", "ft", "remix", "album", "single", "concert"],
                "challenge": ["challenge", "défi", "defi", "24h", "48h", "72h", "1 semaine", "7 jours", "30 jours", "100 jours"],
                "reaction": ["reaction", "réaction", "react", "réagis", "réagir", "avis", "opinion", "review", "critique"],
                "tuto": ["tuto", "tutorial", "astuce", "how to", "conseil", "guide", "apprendre", "formation", "cours", "débutant"],
                "humour": ["humour", "drôle", "blague", "sketch", "comédie", "funny", "meme", "parodie", "comique", "rire"],
                "sport": ["sport", "football", "basket", "tennis", "match", "entrainement", "workout", "musculation", "fitness", "sportif"],
                "tech": ["tech", "technologie", "smartphone", "pc", "ordinateur", "console", "test", "review", "comparatif", "unboxing"],
                "autre": []
            }

            # Initialisation des statistiques par catégorie
            cat_stats = {cat: {
                "count": 0,
                "total_views": 0,
                "total_likes": 0,
                "total_comments": 0,
                "videos": []  # Liste des vidéos pour le logging
            } for cat in categories}

            # Récupération de toutes les vidéos avec pagination améliorée
            max_retries = 3
            retry_delay = 2
            total_videos_retrieved = 0
            total_videos_expected = None

            # Première requête pour obtenir le nombre total de vidéos
            try:
                channel_response = youtube.channels().list(
                    part="statistics",
                    id=channel_id
                ).execute()
                if channel_response["items"]:
                    total_videos_expected = int(channel_response["items"][0]["statistics"]["videoCount"])
                    logger.info(f"Nombre total de vidéos attendu : {total_videos_expected}")
            except Exception as e:
                logger.warning(f"Impossible de récupérer le nombre total de vidéos : {str(e)}")

            # Récupération des vidéos avec pagination
            while True:
                for attempt in range(max_retries):
                    try:
                        search_response = youtube.search().list(
                            channelId=channel_id,
                            part="id,snippet",
                            order="date",
                            maxResults=50,  # Maximum autorisé par l'API
                            type="video",
                            pageToken=nextPageToken
                        ).execute()
                        break
                    except HttpError as e:
                        if "quotaExceeded" in str(e):
                            logger.warning(f"Quota API dépassé, tentative {attempt + 1}/{max_retries}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay * (2 ** attempt))
                                continue
                            raise
                        raise
                    except Exception as e:
                        logger.error(f"Erreur lors de la récupération des vidéos : {str(e)}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))
                            continue
                        raise

                items = search_response.get("items", [])
                if not items:
                    break

                for item in items:
                    published_at = dateutil.parser.parse(item["snippet"]["publishedAt"])
                    if cutoff and published_at < cutoff:
                        logger.debug(f"Vidéo {item['id']['videoId']} ignorée car trop ancienne ({published_at})")
                        continue

                    video_id = item["id"]["videoId"]
                    video_ids.append(video_id)
                    video_info.append({
                        "videoId": video_id,
                        "title": item["snippet"]["title"],
                        "publishedAt": published_at,
                        "description": item["snippet"]["description"]
                    })
                    total_videos_retrieved += 1

                nextPageToken = search_response.get("nextPageToken")
                if not nextPageToken:
                    break

                # Vérification si on a atteint le nombre total de vidéos attendu
                if total_videos_expected and total_videos_retrieved >= total_videos_expected:
                    logger.info(f"Nombre total de vidéos atteint : {total_videos_retrieved}")
                    break

            logger.info(f"Nombre total de vidéos récupérées : {total_videos_retrieved}")
            if total_videos_expected and total_videos_retrieved < total_videos_expected:
                logger.warning(f"Écart détecté : {total_videos_expected - total_videos_retrieved} vidéos manquantes")

            if not video_ids:
                logger.warning(f"Aucune vidéo trouvée pour la période de {period_months} mois")
                return {}

            # Récupération des statistiques détaillées par lots
            all_stats = {}
            batch_size = 50  # Maximum autorisé par l'API
            for i in range(0, len(video_ids), batch_size):
                batch_ids = video_ids[i:i+batch_size]
                for attempt in range(max_retries):
                    try:
                        stats_response = youtube.videos().list(
                            part="statistics,snippet",
                            id=",".join(batch_ids)
                        ).execute()
                        break
                    except HttpError as e:
                        if "quotaExceeded" in str(e):
                            logger.warning(f"Quota API dépassé pour les statistiques, tentative {attempt + 1}/{max_retries}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay * (2 ** attempt))
                                continue
                            raise
                        raise
                    except Exception as e:
                        logger.error(f"Erreur lors de la récupération des statistiques : {str(e)}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))
                            continue
                        raise

                for item in stats_response["items"]:
                    all_stats[item["id"]] = {
                        "statistics": item["statistics"],
                        "snippet": item["snippet"]
                    }

            # Catégorisation et calcul des statistiques
            total_count = 0
            total_views = 0
            total_likes = 0
            total_comments = 0

            for video_id, data in all_stats.items():
                title = data["snippet"]["title"].lower()
                description = data["snippet"]["description"].lower()
                stats = data["statistics"]
                
                # Logging détaillé pour chaque vidéo
                logger.debug(f"Analyse de la vidéo {video_id}: {title}")
                
                found = False
                for cat, keywords in categories.items():
                    if any(kw in title or kw in description for kw in keywords):
                        cat_stats[cat]["count"] += 1
                        cat_stats[cat]["total_views"] += int(stats.get("viewCount", 0))
                        cat_stats[cat]["total_likes"] += int(stats.get("likeCount", 0))
                        cat_stats[cat]["total_comments"] += int(stats.get("commentCount", 0))
                        cat_stats[cat]["videos"].append({
                            "id": video_id,
                            "title": title,
                            "views": int(stats.get("viewCount", 0)),
                            "likes": int(stats.get("likeCount", 0)),
                            "comments": int(stats.get("commentCount", 0))
                        })
                        logger.debug(f"Vidéo {video_id} catégorisée comme {cat}")
                        found = True
                        break

                if not found:
                    cat_stats["autre"]["count"] += 1
                    cat_stats["autre"]["total_views"] += int(stats.get("viewCount", 0))
                    cat_stats["autre"]["total_likes"] += int(stats.get("likeCount", 0))
                    cat_stats["autre"]["total_comments"] += int(stats.get("commentCount", 0))
                    cat_stats["autre"]["videos"].append({
                        "id": video_id,
                        "title": title,
                        "views": int(stats.get("viewCount", 0)),
                        "likes": int(stats.get("likeCount", 0)),
                        "comments": int(stats.get("commentCount", 0))
                    })
                    logger.debug(f"Vidéo {video_id} catégorisée comme 'autre'")

                total_count += 1
                total_views += int(stats.get("viewCount", 0))
                total_likes += int(stats.get("likeCount", 0))
                total_comments += int(stats.get("commentCount", 0))

            # Vérification du comptage
            if total_count != len(video_ids):
                logger.warning(f"Écart dans le comptage : {total_count} vidéos catégorisées sur {len(video_ids)} récupérées")

            # Préparation des résultats
            result = {}
            for cat, vals in cat_stats.items():
                if vals["count"] > 0:
                    avg_views = vals["total_views"] // vals["count"]
                    avg_likes = vals["total_likes"] // vals["count"]
                    avg_comments = vals["total_comments"] // vals["count"]
                    engagement_rate = (avg_likes / avg_views * 100) if avg_views else 0
                    
                    result[cat] = {
                        "count": vals["count"],
                        "total_views": vals["total_views"],
                        "total_likes": vals["total_likes"],
                        "total_comments": vals["total_comments"],
                        "avg_views": avg_views,
                        "avg_likes": avg_likes,
                        "avg_comments": avg_comments,
                        "engagement_rate": engagement_rate
                    }
                    
                    # Logging des statistiques par catégorie
                    logger.info(f"Catégorie {cat}: {vals['count']} vidéos, {avg_views:,} vues moyennes, {engagement_rate:.2f}% d'engagement")

            # Ajout des statistiques globales
            if total_count > 0:
                avg_views = total_views // total_count
                avg_likes = total_likes // total_count
                avg_comments = total_comments // total_count
                engagement_rate = (avg_likes / avg_views * 100) if avg_views else 0
                
                result["Total"] = {
                    "count": total_count,
                    "total_views": total_views,
                    "total_likes": total_likes,
                    "total_comments": total_comments,
                    "avg_views": avg_views,
                    "avg_likes": avg_likes,
                    "avg_comments": avg_comments,
                    "engagement_rate": engagement_rate
                }
                
                logger.info(f"Statistiques globales : {total_count} vidéos, {avg_views:,} vues moyennes, {engagement_rate:.2f}% d'engagement")

            return result

        except Exception as e:
            logger.error(f"Erreur lors de l'analyse des vidéos API: {str(e)}", exc_info=True)
            return {}

    def _analyze_post_stats(self, username):
        if self.use_api:
            return {}
        else:
            return {
                "photos": {
                    "count": 20,
                    "avg_likes": 1000,
                    "avg_comments": 50,
                    "engagement_rate": 3.0
                },
                "videos": {
                    "count": 10,
                    "avg_likes": 2000,
                    "avg_comments": 100,
                    "engagement_rate": 4.0
                }
            }

    def _get_youtube_channel_id(self, username):
        if self.use_api:
            try:
                youtube = get_youtube_client()
                response = youtube.search().list(
                    part="snippet",
                    q=username,
                    type="channel",
                    maxResults=1
                ).execute()
                items = response.get("items", [])
                if items:
                    return items[0]["id"]["channelId"]
                else:
                    return None
            except Exception as e:
                logger.error(f"Erreur lors de la récupération de l'ID YouTube: {str(e)}")
                return None
        else:
            # Simulation
            return "UC_x5XG1OV2P6uZZ5FSM9Ttw"

    def _get_youtube_stats_api(self, channel_id):
        """Récupère les statistiques YouTube via l'API"""
        try:
            youtube = get_youtube_client()
            request = youtube.channels().list(
                part="statistics,snippet",
                id=channel_id
            )
            response = request.execute()
            
            if not response["items"]:
                return None
                
            channel_data = response["items"][0]
            return {
                "channelId": channel_id,
                "title": channel_data["snippet"]["title"],
                "description": channel_data["snippet"]["description"],
                "subscriberCount": int(channel_data["statistics"]["subscriberCount"]),
                "viewCount": int(channel_data["statistics"]["viewCount"]),
                "videoCount": int(channel_data["statistics"]["videoCount"]),
                "likeCount": 0  # YouTube API ne fournit pas directement le nombre de likes
            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des stats YouTube: {str(e)}")
            return None
            
    def _get_instagram_stats_api(self, username):
        """Récupère les statistiques Instagram via l'API"""
        try:
            # Utilisation de l'API RapidAPI pour Instagram
            api_key = os.getenv("INSTAGRAM_RAPID_API_KEY")
            api_host = os.getenv("INSTAGRAM_RAPID_API_HOST")
            
            if not api_key or not api_host:
                logger.warning("Clés d'API Instagram non trouvées")
                return None
                
            # Configuration des headers pour RapidAPI
            headers = {
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": api_host
            }
            
            # Récupération des statistiques du compte Instagram
            url = f"https://{api_host}/user/info"
            params = {"username": username}
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Erreur lors de la récupération des stats Instagram: {response.status_code}")
                return None
                
            data = response.json()
            
            # Extraction des statistiques pertinentes
            return {
                "username": username,
                "followerCount": int(data.get("follower_count", 0)),
                "mediaCount": int(data.get("media_count", 0)),
                "likeCount": int(data.get("like_count", 0))
            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des stats Instagram: {str(e)}")
            return None
            
    def _get_instagram_stats_demo(self, username):
        """Récupère des statistiques Instagram simulées pour le mode démo"""
        # Utilisation des données de fallback pour le mode démo
        stats = self.fallback_data.get_creator_specific_stats(username)
        if not stats:
            stats = self.fallback_data.get_generic_stats("instagram")
            
        return {
            "username": username,
            "followerCount": stats.get("followerCount", 10000),
            "mediaCount": stats.get("mediaCount", 100),
            "likeCount": stats.get("likeCount", 50000)
        }

class ContentCreatorAgent:
    """Agent d'analyse des créateurs de contenu"""
    def __init__(self, use_api=True):
        self.data_manager = DataManager(use_api=use_api)
        
    def get_youtube_stats(self, username):
        """Récupère les statistiques YouTube"""
        return self.data_manager.get_platform_data(username, "youtube")
        
    def get_instagram_stats(self, username):
        """Récupère les statistiques Instagram"""
        return self.data_manager.get_platform_data(username, "instagram")

def display_platform_metrics(platform_data, platform_type):
    """Affiche les métriques de base de la plateforme"""
    logger.info(f"Affichage des métriques pour {platform_type}")
    
    if not platform_data:
        logger.warning(f"Aucune donnée disponible pour {platform_type}")
        st.warning(f"Aucune donnée disponible pour {platform_type}")
        return
        
    metrics = platform_data.get("platform_data", {})
    engagement = platform_data.get("engagement_metrics", {})
    
    logger.debug(f"Métriques brutes : {metrics}")
    logger.debug(f"Engagement : {engagement}")
    
    col1, col2, col3 = st.columns(3)
    
    if platform_type == "youtube":
        with col1:
            subscribers = int(metrics.get('subscriberCount', 0))
            logger.info(f"Nombre d'abonnés YouTube : {subscribers:,}")
            st.metric("Abonnés", f"{subscribers:,}")
        with col2:
            views = int(metrics.get('viewCount', 0))
            logger.info(f"Nombre total de vues : {views:,}")
            st.metric("Vues totales", f"{views:,}")
        with col3:
            videos = int(metrics.get('videoCount', 0))
            logger.info(f"Nombre de vidéos : {videos:,}")
            st.metric("Vidéos", f"{videos:,}")
    else:
        with col1:
            followers = int(metrics.get('followerCount', 0))
            logger.info(f"Nombre d'abonnés Instagram : {followers:,}")
            st.metric("Abonnés", f"{followers:,}")
        with col2:
            posts = int(metrics.get('mediaCount', 0))
            logger.info(f"Nombre de posts : {posts:,}")
            st.metric("Posts", f"{posts:,}")
        with col3:
            likes = int(metrics.get('likeCount', 0))
            logger.info(f"Nombre total de likes : {likes:,}")
            st.metric("Likes", f"{likes:,}")
            
    engagement_rate = engagement.get('overall_engagement_rate', 0)
    if engagement_rate == 0:
        st.metric("Taux d'engagement", f"{engagement_rate:.2f}%", help="Le taux d'engagement n'est pas disponible pour cette chaîne. Il est calculé à partir des likes et abonnés, mais YouTube ne fournit pas toujours cette donnée.")
    else:
        st.metric("Taux d'engagement", f"{engagement_rate:.2f}%")
    
def display_engagement_analysis(engagement_data):
    """Affiche l'analyse d'engagement"""
    logger.info("Affichage de l'analyse d'engagement")
    
    if not engagement_data:
        logger.warning("Données d'engagement non disponibles")
        return
        
    st.subheader("Analyse d'engagement")
    
    benchmark = engagement_data.get("benchmark", "unknown")
    logger.info(f"Benchmark d'engagement : {benchmark}")
    
    benchmark_colors = {
        "excellent": "normal",
        "good": "normal",
        "average": "normal",
        "poor": "inverse",
        "below_average": "inverse",
        "unknown": "off"
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        logger.debug(f"Affichage du benchmark avec couleur : {benchmark_colors.get(benchmark, 'off')}")
        st.metric(
            "Benchmark",
            benchmark.capitalize(),
            delta=None,
            delta_color=benchmark_colors.get(benchmark, "off"),
            help="Le benchmark est basé sur le taux d'engagement calculé. S'il est 'Unknown', cela signifie que le taux d'engagement n'a pas pu être calculé."
        )
        
    with col2:
        industry_avg = engagement_data.get("industry_average", 0)
        logger.info(f"Moyenne du secteur : {industry_avg:.2f}%")
        st.metric(
            "Moyenne du secteur",
            f"{industry_avg:.2f}%",
            delta=None
        )
        
def display_reputation_analysis(reputation_data):
    """Affiche l'analyse de réputation"""
    logger.info("Affichage de l'analyse de réputation")
    
    if not reputation_data:
        logger.warning("Données de réputation non disponibles")
        return
        
    st.subheader("Analyse de réputation")
    
    # Style CSS pour les cartes
    st.markdown("""
    <style>
    .reputation-card {
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }
    .reputation-card:hover {
        transform: translateY(-2px);
    }
    .reputation-title {
        font-size: 1.2em;
        font-weight: 600;
        margin-bottom: 10px;
        color: #333;
    }
    .reputation-value {
        font-size: 2em;
        font-weight: 700;
        margin: 0;
    }
    .reputation-metric {
        font-size: 0.9em;
        color: #666;
        margin-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Couleurs pour les différents niveaux
    risk_colors = {
        "excellent": "#4CAF50",
        "bon": "#8BC34A",
        "moyen": "#FFC107",
        "à surveiller": "#FF9800",
        "risqué": "#F44336",
        "unknown": "#9E9E9E"
    }
    
    # Métriques principales
    col1, col2, col3 = st.columns(3)
    
    with col1:
        risk_level = reputation_data.get('risk_level', 'unknown')
        st.markdown(f"""
        <div class="reputation-card" style="background-color: {risk_colors.get(risk_level, '#9E9E9E')}; color: white;">
            <div class="reputation-title">Niveau de réputation</div>
            <div class="reputation-value">{risk_level.capitalize()}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        metrics = reputation_data.get("metrics", {})
        avg_sentiment = metrics.get("average_sentiment", 0)
        sentiment_color = "#4CAF50" if avg_sentiment > 0.2 else "#F44336" if avg_sentiment < -0.2 else "#FFC107"
        st.markdown(f"""
        <div class="reputation-card" style="background-color: {sentiment_color}; color: white;">
            <div class="reputation-title">Sentiment moyen</div>
            <div class="reputation-value">{avg_sentiment:.2f}</div>
            <div class="reputation-metric">-1 (négatif) à +1 (positif)</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        controversies = len(reputation_data.get("controversies", []))
        controversy_color = "#4CAF50" if controversies == 0 else "#F44336" if controversies > 2 else "#FFC107"
        st.markdown(f"""
        <div class="reputation-card" style="background-color: {controversy_color}; color: white;">
            <div class="reputation-title">Controverses</div>
            <div class="reputation-value">{controversies}</div>
            <div class="reputation-metric">articles détectés</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Résumé avec icône
    summary = reputation_data.get("summary", "")
    st.markdown(f"""
    <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 8px;">
        <span style="font-size: 1.2em;">📊</span> {summary}
    </div>
    """, unsafe_allow_html=True)
    
    # Métriques détaillées avec un design plus épuré
    metrics = reputation_data.get("metrics", {})
    if metrics:
        with st.expander("📈 Détails de l'analyse", expanded=False):
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; margin: 10px 0;">
                <div style="flex: 1; text-align: center; padding: 10px; background-color: #f8f9fa; border-radius: 8px; margin: 0 5px;">
                    <div style="font-size: 1.5em; font-weight: bold;">{metrics.get('articles_analyzed', 0)}</div>
                    <div style="color: #666;">Articles analysés</div>
                </div>
                <div style="flex: 1; text-align: center; padding: 10px; background-color: #f8f9fa; border-radius: 8px; margin: 0 5px;">
                    <div style="font-size: 1.5em; font-weight: bold;">{metrics.get('controversy_score', 0):.2f}</div>
                    <div style="color: #666;">Score de controverse</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Articles controversés avec un design plus moderne
    controversies = reputation_data.get("controversies", [])
    if controversies:
        with st.expander(f"⚠️ Controverses ({len(controversies)})", expanded=False):
            for controversy in controversies:
                st.markdown(f"""
                <div style="margin: 10px 0; padding: 15px; background-color: #fff3f3; border-radius: 8px; border-left: 4px solid #F44336;">
                    <div style="font-weight: bold; margin-bottom: 5px;">{controversy.get('title')}</div>
                    <div style="color: #666; font-size: 0.9em;">
                        📅 {controversy.get('date', 'Inconnue')} | 
                        🔍 {', '.join(controversy.get('keywords', []))}
                    </div>
                    <a href="{controversy.get('url', '#')}" style="color: #2196F3; text-decoration: none; font-size: 0.9em;">Lire l'article →</a>
                </div>
                """, unsafe_allow_html=True)
    
    # Tous les articles avec un design plus épuré
    all_articles = reputation_data.get("all_articles", [])
    if all_articles:
        with st.expander(f"📰 Tous les articles ({len(all_articles)})", expanded=False):
            sorted_articles = sorted(all_articles, key=lambda x: x.get('sentiment', 0), reverse=True)
            
            for article in sorted_articles:
                sentiment = article.get('sentiment', 0)
                sentiment_color = "#4CAF50" if sentiment > 0.2 else "#F44336" if sentiment < -0.2 else "#FFC107"
                st.markdown(f"""
                <div style="margin: 10px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px;">
                    <div style="font-weight: bold; margin-bottom: 5px;">{article.get('title')}</div>
                    <div style="color: #666; font-size: 0.9em;">
                        📅 {article.get('date', 'Inconnue')} | 
                        <span style="color: {sentiment_color};">🎭 {sentiment:.2f}</span>
                    </div>
                    <a href="{article.get('url', '#')}" style="color: #2196F3; text-decoration: none; font-size: 0.9em;">Lire l'article →</a>
                </div>
                """, unsafe_allow_html=True)

def display_content_stats(stats_data, content_type):
    """Affiche les statistiques de contenu"""
    logger.info(f"Affichage des statistiques {content_type}")
    
    if not stats_data:
        logger.warning(f"Aucune statistique disponible pour {content_type}")
        st.info("Aucune statistique disponible en mode API pour ce créateur.")
        return
        
    st.subheader(f"Statistiques {content_type}")
    
    for category, data in stats_data.items():
        logger.debug(f"Statistiques pour la catégorie {category}: {data}")
        with st.expander(category.capitalize()):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                count = data.get("count", 0)
                logger.info(f"Nombre de {category}: {count}")
                st.metric("Nombre", count)
            with col2:
                avg_views = int(data.get("avg_views", 0))
                logger.info(f"Vues moyennes pour {category}: {avg_views:,}")
                st.metric("Vues moyennes", f"{avg_views:,}")
            with col3:
                avg_likes = int(data.get("avg_likes", 0))
                logger.info(f"Likes moyens pour {category}: {avg_likes:,}")
                st.metric("Likes moyens", f"{avg_likes:,}")
            with col4:
                engagement_rate = data.get("engagement_rate", 0)
                logger.info(f"Taux d'engagement pour {category}: {engagement_rate:.2f}%")
                st.metric("Taux d'engagement", f"{engagement_rate:.2f}%")
                
def main():
    """Fonction principale de l'application"""
    try:
        logger.info("=== DÉMARRAGE DE L'APPLICATION ===")
        st.title("Analyseur de Créateurs de Contenu")
        
        # Configuration de l'interface
        mode = st.radio(
            "Mode d'exécution",
            ["API réelle (données live)", "Démo (fausses données)"],
            help="Choisissez entre les données en direct ou les données de démonstration"
        )
        use_api = (mode == "API réelle (données live)")
        logger.info(f"Mode sélectionné : {'API' if use_api else 'Démo'}")
        
        platform = st.selectbox(
            "Plateforme",
            ["YouTube", "Instagram"],
            help="Sélectionnez la plateforme à analyser"
        )
        logger.info(f"Plateforme sélectionnée : {platform}")
        
        username = st.text_input(
            "Nom d'utilisateur",
            help=f"Entrez le nom d'utilisateur {platform}"
        )
        logger.info(f"Nom d'utilisateur saisi : {username}")
        
        # Sélecteur de période
        period_label = st.selectbox(
            "Période d'analyse des vidéos",
            ["3 derniers mois", "6 derniers mois", "12 derniers mois", "Toutes les vidéos"],
            help="Choisissez la période sur laquelle calculer les statistiques détaillées."
        )
        period_months = {
            "3 derniers mois": 3,
            "6 derniers mois": 6,
            "12 derniers mois": 12,
            "Toutes les vidéos": None
        }[period_label]
        
        if st.button("Analyser"):
            if not username:
                st.error("Veuillez entrer un nom d'utilisateur")
                logger.warning("Tentative d'analyse sans nom d'utilisateur")
                return
                
            try:
                with st.spinner("Analyse en cours..."):
                    logger.info(f"Début de l'analyse pour {username} sur {platform}")
                    agent = ContentCreatorAgent(use_api=use_api)
                    
                    if platform == "YouTube":
                        data = agent.get_youtube_stats(username)
                    else:
                        data = agent.get_instagram_stats(username)
                        
                    if not data:
                        st.error(f"Impossible de récupérer les données pour {username}")
                        logger.error(f"Impossible de récupérer les données pour {username}")
                        return
                        
                    logger.info("Affichage des résultats")
                    
                    # Traitement des données
                    engagement = data.get("engagement_metrics", {})
                    video_stats = None
                    
                    if platform == "YouTube":
                        channel_id = data.get("platform_data", {}).get("channelId")
                        if channel_id:
                            video_stats = agent.data_manager._analyze_video_stats(
                                channel_id,
                                period_months=period_months
                            )
                    
                    # Mise à jour du taux d'engagement si nécessaire
                    engagement_rate = engagement.get("overall_engagement_rate", 0)
                    if engagement_rate == 0 and video_stats:
                        best_cat = max(video_stats.items(), key=lambda x: x[1]["count"])[1]
                        if best_cat.get("engagement_rate", 0) > 0:
                            engagement["overall_engagement_rate"] = best_cat["engagement_rate"]
                            engagement["benchmark"] = agent.data_manager._get_engagement_benchmark(best_cat["engagement_rate"])
                    
                    # Affichage des résultats
                    display_platform_metrics(data, platform.lower())
                    display_engagement_analysis(engagement)
                    display_reputation_analysis(data.get("reputation_data", {}))
                    
                    if platform == "YouTube" and video_stats:
                        display_content_stats(video_stats, f"des vidéos ({period_label})")
                    elif platform == "Instagram":
                        display_content_stats(data.get("post_stats", {}), "des posts")
                        
            except HttpError as e:
                if API_QUOTA_EXCEEDED_ERROR in str(e):
                    st.error("Le quota d'API a été dépassé. Veuillez réessayer plus tard ou passer en mode démo.")
                else:
                    st.error(f"Une erreur est survenue lors de l'analyse : {str(e)}")
                logger.error(f"Erreur HTTP lors de l'analyse : {str(e)}")
            except Exception as e:
                st.error(f"Une erreur inattendue est survenue : {str(e)}")
                logger.error(f"Erreur lors de l'analyse : {str(e)}", exc_info=True)
                
    except Exception as e:
        st.error("Une erreur critique est survenue. Veuillez réessayer.")
        logger.critical(f"Erreur critique : {str(e)}", exc_info=True)
    finally:
        logger.info("=== FIN DE L'APPLICATION ===")

if __name__ == "__main__":
    main()