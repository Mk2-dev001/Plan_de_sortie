#!/usr/bin/env python3
"""
Script de diagnostic IAM pour les points d'accès S3
Aide à identifier les problèmes de permissions
"""

import boto3
import json
import sys
from botocore.exceptions import ClientError, NoCredentialsError

class IAMDiagnostic:
    def __init__(self, region='eu-west-1'):
        self.region = region
        self.iam_client = None
        self.sts_client = None
        
    def initialize_clients(self):
        """Initialise les clients IAM et STS"""
        try:
            print("🔧 Initialisation des clients IAM et STS...")
            self.iam_client = boto3.client('iam', region_name=self.region)
            self.sts_client = boto3.client('sts', region_name=self.region)
            print("✅ Clients initialisés")
            return True
        except Exception as e:
            print(f"❌ Erreur d'initialisation: {e}")
            return False
    
    def get_current_user_info(self):
        """Récupère les informations de l'utilisateur actuel"""
        print("\n👤 Informations de l'utilisateur actuel:")
        try:
            response = self.sts_client.get_caller_identity()
            user_id = response.get('UserId', 'N/A')
            account = response.get('Account', 'N/A')
            arn = response.get('Arn', 'N/A')
            
            print(f"   User ID: {user_id}")
            print(f"   Account: {account}")
            print(f"   ARN: {arn}")
            
            return response
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return None
    
    def check_user_policies(self, user_arn):
        """Vérifie les politiques attachées à l'utilisateur"""
        print("\n📋 Politiques de l'utilisateur:")
        
        try:
            # Extraire le nom d'utilisateur de l'ARN
            if 'user/' in user_arn:
                username = user_arn.split('user/')[-1]
            else:
                print("   ⚠️  Impossible d'extraire le nom d'utilisateur")
                return
            
            # Politiques inline
            print("   Politiques inline:")
            try:
                inline_policies = self.iam_client.list_user_policies(UserName=username)
                for policy in inline_policies.get('PolicyNames', []):
                    print(f"     - {policy}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
                    print("     ❌ Access Denied - Impossible de lister les politiques inline")
                else:
                    print(f"     ❌ Erreur: {e.response['Error']['Code']}")
            
            # Politiques attachées
            print("   Politiques attachées:")
            try:
                attached_policies = self.iam_client.list_attached_user_policies(UserName=username)
                for policy in attached_policies.get('AttachedPolicies', []):
                    print(f"     - {policy['PolicyName']} ({policy['PolicyArn']})")
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
                    print("     ❌ Access Denied - Impossible de lister les politiques attachées")
                else:
                    print(f"     ❌ Erreur: {e.response['Error']['Code']}")
                    
        except Exception as e:
            print(f"   ❌ Erreur lors de la vérification des politiques: {e}")
    
    def check_group_policies(self, user_arn):
        """Vérifie les politiques des groupes de l'utilisateur"""
        print("\n👥 Politiques des groupes:")
        
        try:
            if 'user/' in user_arn:
                username = user_arn.split('user/')[-1]
            else:
                print("   ⚠️  Impossible d'extraire le nom d'utilisateur")
                return
            
            # Groupes de l'utilisateur
            try:
                groups = self.iam_client.list_groups_for_user(UserName=username)
                for group in groups.get('Groups', []):
                    group_name = group['GroupName']
                    print(f"   Groupe: {group_name}")
                    
                    # Politiques inline du groupe
                    try:
                        group_inline = self.iam_client.list_group_policies(GroupName=group_name)
                        for policy in group_inline.get('PolicyNames', []):
                            print(f"     - Politique inline: {policy}")
                    except ClientError:
                        print("     - Impossible de lister les politiques inline")
                    
                    # Politiques attachées au groupe
                    try:
                        group_attached = self.iam_client.list_attached_group_policies(GroupName=group_name)
                        for policy in group_attached.get('AttachedPolicies', []):
                            print(f"     - Politique attachée: {policy['PolicyName']}")
                    except ClientError:
                        print("     - Impossible de lister les politiques attachées")
                        
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
                    print("   ❌ Access Denied - Impossible de lister les groupes")
                else:
                    print(f"   ❌ Erreur: {e.response['Error']['Code']}")
                    
        except Exception as e:
            print(f"   ❌ Erreur lors de la vérification des groupes: {e}")
    
    def suggest_s3_permissions(self):
        """Suggère les permissions nécessaires pour S3 Access Points"""
        print("\n💡 Permissions recommandées pour S3 Access Points:")
        print("   Politique IAM minimale nécessaire:")
        
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetAccessPoint",
                        "s3:ListAccessPoints",
                        "s3:GetAccessPointPolicy",
                        "s3:GetAccessPointPolicyStatus"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket"
                    ],
                    "Resource": [
                        "arn:aws:s3:eu-west-1:488643426355:accesspoint/accesspoint-megascope",
                        "arn:aws:s3:eu-west-1:488643426355:accesspoint/accesspoint-megascope/*"
                    ]
                }
            ]
        }
        
        print(json.dumps(policy, indent=2))
    
    def run_diagnostic(self):
        """Lance le diagnostic complet"""
        print("🔍 Diagnostic IAM pour S3 Access Points")
        print("=" * 50)
        
        if not self.initialize_clients():
            return False
        
        # Informations utilisateur
        user_info = self.get_current_user_info()
        if not user_info:
            return False
        
        # Vérifications des politiques
        self.check_user_policies(user_info['Arn'])
        self.check_group_policies(user_info['Arn'])
        
        # Suggestions
        self.suggest_s3_permissions()
        
        print("\n🔧 Actions recommandées:")
        print("   1. Vérifiez que votre utilisateur a les permissions s3:GetAccessPoint")
        print("   2. Vérifiez que vous êtes dans le bon compte AWS (488643426355)")
        print("   3. Contactez votre administrateur AWS pour vérifier les politiques IAM")
        print("   4. Vérifiez que le point d'accès existe dans la région eu-west-1")
        
        return True


def main():
    """Fonction principale"""
    try:
        diagnostic = IAMDiagnostic()
        diagnostic.run_diagnostic()
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 