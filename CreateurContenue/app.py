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
    level=logging.INFO,  # Changé à INFO pour réduire les logs verbeux
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log'),  # Log dans un fichier
        logging.StreamHandler()  # Log dans la console
    ]
)
logger = logging.getLogger(__name__)

# Désactiver les logs verbeux des bibliothèques externes
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

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
    def __init__(self, cache_duration=3600):
        self.cache = {}
        self.cache_duration = cache_duration
        self.last_cleanup = time.time()

    def get(self, key):
        """Récupère une valeur du cache"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_duration:
                return data
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        """Stocke une valeur dans le cache"""
        self.cache[key] = (value, time.time())
        self._cleanup_if_needed()

    def _cleanup_if_needed(self):
        """Nettoie le cache si nécessaire"""
        current_time = time.time()
        if current_time - self.last_cleanup > 3600:  # Nettoyage toutes les heures
            self.cache = {k: v for k, v in self.cache.items() 
                         if current_time - v[1] < self.cache_duration}
            self.last_cleanup = current_time

class APIRequestManager:
    """Gestionnaire de requêtes API avec retry et rate limiting"""
    def __init__(self, max_retries=3, retry_delay=1):
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
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.retry_delay * (attempt + 1))
                logger.warning(f"Tentative {attempt + 1} échouée pour {platform}: {str(e)}")

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
        cache_key = f"{platform}_{username}_{'api' if self.use_api else 'demo'}"
        cached_data = self.cache.get(cache_key)
        
        if cached_data:
            return cached_data
            
        try:
            if platform.lower() == "youtube":
                data = self._fetch_youtube_data(username)
            else:
                data = self._fetch_instagram_data(username)
                
            if data:
                self.cache.set(cache_key, data)
                return data
                
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données {platform}: {str(e)}")
            if self.use_api:
                return None
            # Toujours retourner la structure complète attendue
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
            return None
        
        if self.use_api:
            stats = self.request_manager.execute_request(
                "youtube",
                lambda: self._get_youtube_stats_api(channel_id)
            )
        else:
            stats = self._get_youtube_stats_demo("demo")
        
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
        
    def _analyze_reputation(self, username):
        """Analyse la réputation du créateur (API ou démo)"""
        if self.use_api and self.news_api_key:
            try:
                # Recherche d'articles polémiques avec NewsAPI
                url = f'https://newsapi.org/v2/everything?q={username}&language=fr&sortBy=relevancy&pageSize=5&apiKey={self.news_api_key}'
                response = requests.get(url)
                if response.status_code == 200:
                    articles = response.json().get("articles", [])
                    controversies = []
                    summary = "Aucune polémique détectée."
                    for article in articles:
                        if any(mot in article["title"].lower() for mot in ["polémique", "scandale", "controverse", "bad buzz", "accusé", "racisme", "harcèlement", "agression", "plainte", "procès"]):
                            controversies.append({"title": article["title"], "url": article["url"]})
                    if controversies:
                        summary = f"{len(controversies)} polémique(s) détectée(s) dans la presse."
                    return {
                        "score": "Non disponible",
                        "risk_level": "unknown" if not controversies else "high",
                        "status": "Non disponible",
                        "summary": summary,
                        "controversies": controversies
                    }
                    # Si pas de controverse détectée
                    return {
                        "score": "Non disponible",
                        "risk_level": "low",
                        "status": "Non disponible",
                        "summary": summary,
                        "controversies": []
                    }
                else:
                    logger.warning(f"Erreur NewsAPI: {response.status_code}")
                    return {
                        "score": "Non disponible",
                        "risk_level": "unknown",
                        "status": "Non disponible",
                        "summary": "Aucune donnée de réputation disponible (erreur NewsAPI)",
                        "controversies": []
                    }
            except Exception as e:
                logger.error(f"Erreur lors de l'analyse de réputation NewsAPI: {str(e)}")
                return {
                    "score": "Non disponible",
                    "risk_level": "unknown",
                    "status": "Non disponible",
                    "summary": "Aucune donnée de réputation disponible (erreur NewsAPI)",
                    "controversies": []
                }
        else:
            # Mode démo (simulé)
            return {
                "score": 85,
                "risk_level": "low",
                "status": "positive",
                "summary": "Aucune polémique majeure détectée.",
                "controversies": [
                    {"title": "Polémique sur la vidéo X", "url": "https://exemple.com/article1"}
                ]
            }
    
    def _analyze_video_stats(self, channel_id, period_months=None):
        if self.use_api:
            try:
                youtube = get_youtube_client()
                # Récupérer les vidéos sur la période demandée
                video_ids = []
                video_info = []
                nextPageToken = None
                now = datetime.datetime.utcnow()
                cutoff = None
                if period_months:
                    cutoff = now - datetime.timedelta(days=30*period_months)
                for _ in range(10):  # Jusqu'à 250 vidéos max (10 pages)
                    search_response = youtube.search().list(
                        channelId=channel_id,
                        part="id,snippet",
                        order="date",
                        maxResults=25,
                        type="video",
                        pageToken=nextPageToken
                    ).execute()
                    for item in search_response["items"]:
                        published_at = dateutil.parser.parse(item["snippet"]["publishedAt"]).replace(tzinfo=None)
                        if cutoff and published_at < cutoff:
                            continue
                        video_ids.append(item["id"]["videoId"])
                        video_info.append({
                            "videoId": item["id"]["videoId"],
                            "title": item["snippet"]["title"],
                            "publishedAt": published_at
                        })
                    nextPageToken = search_response.get("nextPageToken")
                    if not nextPageToken:
                        break
                if not video_ids:
                    return {}
                # Récupérer les stats des vidéos
                stats_response = youtube.videos().list(
                    part="statistics,snippet",
                    id=",".join(video_ids)
                ).execute()
                # Catégorisation enrichie par mots-clés
                categories = {
                    "gaming": ["gaming", "jeu", "game", "minecraft", "fortnite", "gta", "call of duty", "fifa"],
                    "vlog": ["vlog", "daily", "journee", "routine", "voyage", "travel"],
                    "music": ["music", "musique", "clip", "cover", "chanson", "song"],
                    "challenge": ["challenge", "défi", "defi"],
                    "reaction": ["reaction", "réaction"],
                    "tuto": ["tuto", "tutorial", "astuce", "how to", "conseil"],
                    "humour": ["humour", "drôle", "blague", "sketch", "comédie", "funny"],
                    "sport": ["sport", "football", "basket", "tennis", "match", "entrainement", "workout"],
                    "autre": []
                }
                cat_stats = {cat: {"count": 0, "total_views": 0, "total_likes": 0, "total_comments": 0} for cat in categories}
                for item in stats_response["items"]:
                    title = item["snippet"]["title"].lower()
                    stats = item["statistics"]
                    found = False
                    for cat, keywords in categories.items():
                        if any(kw in title for kw in keywords):
                            cat_stats[cat]["count"] += 1
                            cat_stats[cat]["total_views"] += int(stats.get("viewCount", 0))
                            cat_stats[cat]["total_likes"] += int(stats.get("likeCount", 0))
                            cat_stats[cat]["total_comments"] += int(stats.get("commentCount", 0))
                            found = True
                            break
                    if not found:
                        cat_stats["autre"]["count"] += 1
                        cat_stats["autre"]["total_views"] += int(stats.get("viewCount", 0))
                        cat_stats["autre"]["total_likes"] += int(stats.get("likeCount", 0))
                        cat_stats["autre"]["total_comments"] += int(stats.get("commentCount", 0))
                # Calcul des moyennes et taux d'engagement par catégorie
                result = {}
                for cat, vals in cat_stats.items():
                    if vals["count"] > 0:
                        avg_views = vals["total_views"] // vals["count"]
                        avg_likes = vals["total_likes"] // vals["count"]
                        avg_comments = vals["total_comments"] // vals["count"]
                        engagement_rate = (avg_likes / avg_views * 100) if avg_views else 0
                        result[cat] = {
                            "count": vals["count"],
                            "avg_views": avg_views,
                            "avg_likes": avg_likes,
                            "avg_comments": avg_comments,
                            "engagement_rate": engagement_rate
                        }
                return result
            except Exception as e:
                logger.error(f"Erreur lors de l'analyse des vidéos API: {str(e)}")
                return {}
        else:
            # Simulation d'analyse des vidéos
            return {
                "gaming": {
                    "count": 10,
                    "avg_views": 100000,
                    "avg_likes": 5000,
                    "engagement_rate": 5.0
                },
                "vlog": {
                    "count": 5,
                    "avg_views": 50000,
                    "avg_likes": 2500,
                    "engagement_rate": 5.0
                }
            }
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
    
    risk_level = reputation_data.get("risk_level", "unknown")
    logger.info(f"Niveau de risque : {risk_level}")
    
    risk_colors = {
        "low": "normal",
        "medium": "normal",
        "high": "inverse",
        "unknown": "off"
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        score = reputation_data.get('score', 'Non disponible')
        logger.info(f"Score de réputation : {score}/100")
        st.metric(
            "Score de réputation",
            f"{score}/100" if score != 'Non disponible' else score,
            delta=None,
            delta_color=risk_colors.get(risk_level, "off"),
            help="Le score de réputation n'est pas disponible car aucune API spécialisée n'est connectée."
        )
        
    with col2:
        logger.debug(f"Affichage du niveau de risque avec couleur : {risk_colors.get(risk_level, 'off')}")
        st.metric(
            "Niveau de risque",
            risk_level.capitalize(),
            delta=None,
            delta_color=risk_colors.get(risk_level, "off"),
            help="Le niveau de risque est basé sur le score de réputation et la détection de polémiques."
        )
    # Résumé (toujours affiché)
    summary = reputation_data.get("summary", "")
    st.info(f"Résumé : {summary if summary else 'Aucune donnée de réputation disponible.'}")
    # Controverses
    if reputation_data.get("controversies"):
        controversies = reputation_data["controversies"]
        logger.warning(f"Controverses détectées : {controversies}")
        st.warning("Controverses détectées")
        for controversy in controversies:
            titre = controversy.get("title", "Article")
            url = controversy.get("url", "#")
            st.markdown(f"- [{titre}]({url})")
            
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
    logger.info("=== DÉMARRAGE DE L'APPLICATION ===")
    st.title("Analyseur de Créateurs de Contenu")
    
    mode = st.radio(
        "Mode d'exécution",
        ["API réelle (données live)", "Démo (fausses données)"]
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
    period_months = {"3 derniers mois": 3, "6 derniers mois": 6, "12 derniers mois": 12, "Toutes les vidéos": None}[period_label]
    
    if st.button("Analyser"):
        if not username:
            logger.warning("Tentative d'analyse sans nom d'utilisateur")
            st.error("Veuillez entrer un nom d'utilisateur")
            return
            
        try:
            logger.info(f"Début de l'analyse pour {username} sur {platform}")
            agent = ContentCreatorAgent(use_api=use_api)
            
            if platform == "YouTube":
                data = agent.get_youtube_stats(username)
            else:
                data = agent.get_instagram_stats(username)
                
            if not data:
                logger.error(f"Impossible de récupérer les données pour {username}")
                st.error(f"Impossible de récupérer les données pour {username}")
                return
                
            logger.info("Affichage des résultats")
            # Utiliser le taux d'engagement des vidéos récentes si le global est à 0
            engagement = data.get("engagement_metrics", {})
            # On récupère les stats vidéos sur la période choisie
            video_stats = agent.data_manager._analyze_video_stats(
                data["platform_data"].get("channelId", data.get("platform_data", {}).get("channelId", None)),
                period_months=period_months
            ) if platform == "YouTube" else {}
            engagement_rate = engagement.get("overall_engagement_rate", 0)
            # On prend le taux d'engagement de la catégorie la plus représentée si le global est à 0
            if engagement_rate == 0 and video_stats:
                best_cat = max(video_stats.items(), key=lambda x: x[1]["count"])[1]
                if best_cat.get("engagement_rate", 0) > 0:
                    engagement["overall_engagement_rate"] = best_cat["engagement_rate"]
                    engagement["benchmark"] = agent.data_manager._get_engagement_benchmark(best_cat["engagement_rate"])
            display_platform_metrics(data, platform.lower())
            display_engagement_analysis(engagement)
            display_reputation_analysis(data.get("reputation_data", {}))
            
            if platform == "YouTube":
                display_content_stats(video_stats, f"des vidéos ({period_label})")
            else:
                display_content_stats(data.get("post_stats", {}), "des posts")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse : {str(e)}", exc_info=True)
            st.error(f"Une erreur est survenue : {str(e)}")
            
    logger.info("=== FIN DE L'APPLICATION ===")
            
if __name__ == "__main__":
    main() 