"""Email service for sending verification and welcome emails."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import structlog

from app.core.config import settings

logger = structlog.get_logger()


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> bool:
    """
    Send an email using SMTP.

    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        text_content: Plain text fallback content

    Returns:
        True if email sent successfully, False otherwise
    """
    # Check if SMTP is configured
    if not settings.SMTP_HOST or not settings.EMAILS_FROM_EMAIL:
        logger.warning(
            "email.not_configured",
            reason="SMTP not configured, email not sent",
            to_email=to_email,
        )
        return False

    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Add plain text part if provided
        if text_content:
            part1 = MIMEText(text_content, "plain")
            msg.attach(part1)

        # Add HTML part
        part2 = MIMEText(html_content, "html")
        msg.attach(part2)

        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())

        logger.info(
            "email.sent",
            to_email=to_email,
            subject=subject,
        )
        return True

    except Exception as e:
        logger.error(
            "email.send_failed",
            to_email=to_email,
            subject=subject,
            error=str(e),
        )
        return False


def get_verification_email_html(full_name: str, verification_url: str) -> str:
    """
    Get HTML template for email verification.

    Args:
        full_name: User's full name
        verification_url: URL for email verification

    Returns:
        HTML email content
    """
    return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vérifiez votre email - CloudWaste</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center;">
                            <h1 style="margin: 0; color: #1f2937; font-size: 28px; font-weight: 700;">
                                🛡️ CloudWaste
                            </h1>
                            <p style="margin: 10px 0 0; color: #6b7280; font-size: 14px;">
                                Optimisation des coûts Cloud
                            </p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px;">
                            <h2 style="margin: 0 0 20px; color: #1f2937; font-size: 22px; font-weight: 600;">
                                Bienvenue {full_name} ! 👋
                            </h2>
                            <p style="margin: 0 0 15px; color: #374151; font-size: 16px; line-height: 1.6;">
                                Merci de vous être inscrit sur <strong>CloudWaste</strong>. Pour commencer à optimiser vos coûts cloud, veuillez confirmer votre adresse email en cliquant sur le bouton ci-dessous :
                            </p>

                            <!-- CTA Button -->
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{verification_url}" style="display: inline-block; padding: 14px 32px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                                            ✉️ Vérifier mon email
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 20px 0 10px; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                Ou copiez ce lien dans votre navigateur :
                            </p>
                            <p style="margin: 0; color: #2563eb; font-size: 13px; word-break: break-all;">
                                {verification_url}
                            </p>

                            <!-- Expiration notice -->
                            <div style="margin: 30px 0; padding: 16px; background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
                                <p style="margin: 0; color: #92400e; font-size: 14px;">
                                    ⏱️ <strong>Ce lien expire dans 7 jours.</strong><br>
                                    Après ce délai, votre compte sera automatiquement supprimé.
                                </p>
                            </div>

                            <p style="margin: 20px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                Si vous n'avez pas créé de compte CloudWaste, vous pouvez ignorer cet email.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; color: #9ca3af; font-size: 12px; text-align: center; line-height: 1.5;">
                                Cet email a été envoyé par <strong>CloudWaste</strong><br>
                                © 2025 CloudWaste. Tous droits réservés.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def get_verification_email_text(full_name: str, verification_url: str) -> str:
    """
    Get plain text version for email verification.

    Args:
        full_name: User's full name
        verification_url: URL for email verification

    Returns:
        Plain text email content
    """
    return f"""
Bienvenue {full_name} !

Merci de vous être inscrit sur CloudWaste. Pour commencer à optimiser vos coûts cloud, veuillez confirmer votre adresse email en cliquant sur le lien ci-dessous :

{verification_url}

⏱️ Ce lien expire dans 7 jours. Après ce délai, votre compte sera automatiquement supprimé.

Si vous n'avez pas créé de compte CloudWaste, vous pouvez ignorer cet email.

---
Cet email a été envoyé par CloudWaste
© 2025 CloudWaste. Tous droits réservés.
"""


def send_verification_email(
    email: str,
    full_name: str,
    verification_token: str,
) -> bool:
    """
    Send email verification to user.

    Args:
        email: User email address
        full_name: User's full name
        verification_token: Verification token

    Returns:
        True if email sent successfully, False otherwise
    """
    verification_url = f"{settings.FRONTEND_URL}/auth/verify-email/{verification_token}"

    html_content = get_verification_email_html(full_name, verification_url)
    text_content = get_verification_email_text(full_name, verification_url)

    return send_email(
        to_email=email,
        subject="Vérifiez votre email - CloudWaste",
        html_content=html_content,
        text_content=text_content,
    )


def get_welcome_email_html(full_name: str) -> str:
    """
    Get HTML template for welcome email.

    Args:
        full_name: User's full name

    Returns:
        HTML email content
    """
    app_url = settings.FRONTEND_URL

    return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bienvenue sur CloudWaste</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center;">
                            <h1 style="margin: 0; color: #1f2937; font-size: 32px; font-weight: 700;">
                                🎉 Félicitations !
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px;">
                            <h2 style="margin: 0 0 20px; color: #1f2937; font-size: 22px; font-weight: 600;">
                                Votre compte est activé, {full_name} !
                            </h2>
                            <p style="margin: 0 0 15px; color: #374151; font-size: 16px; line-height: 1.6;">
                                Votre adresse email a été vérifiée avec succès. Vous pouvez maintenant accéder à toutes les fonctionnalités de <strong>CloudWaste</strong> :
                            </p>

                            <!-- Features list -->
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 25px 0;">
                                <tr>
                                    <td style="padding: 12px 0;">
                                        <span style="font-size: 24px;">📊</span>
                                        <strong style="color: #1f2937; font-size: 15px; margin-left: 10px;">Scans automatiques</strong>
                                        <p style="margin: 5px 0 0 44px; color: #6b7280; font-size: 14px;">Détection des ressources orphelines AWS et Azure</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0;">
                                        <span style="font-size: 24px;">💰</span>
                                        <strong style="color: #1f2937; font-size: 15px; margin-left: 10px;">Économies identifiées</strong>
                                        <p style="margin: 5px 0 0 44px; color: #6b7280; font-size: 14px;">Estimation précise des coûts gaspillés</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0;">
                                        <span style="font-size: 24px;">🤖</span>
                                        <strong style="color: #1f2937; font-size: 15px; margin-left: 10px;">Assistant IA FinOps</strong>
                                        <p style="margin: 5px 0 0 44px; color: #6b7280; font-size: 14px;">Conseils personnalisés par Claude AI</p>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{app_url}/auth/login" style="display: inline-block; padding: 14px 32px; background-color: #10b981; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                                            🚀 Accéder à CloudWaste
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <!-- Next steps -->
                            <div style="margin: 30px 0; padding: 20px; background-color: #f0f9ff; border-left: 4px solid #2563eb; border-radius: 4px;">
                                <p style="margin: 0 0 10px; color: #1e40af; font-size: 15px; font-weight: 600;">
                                    🎯 Prochaines étapes :
                                </p>
                                <ol style="margin: 10px 0 0; padding-left: 20px; color: #1e3a8a; font-size: 14px; line-height: 1.8;">
                                    <li>Connectez votre compte AWS ou Azure</li>
                                    <li>Lancez votre premier scan</li>
                                    <li>Découvrez vos économies potentielles</li>
                                    <li>Discutez avec l'assistant IA pour optimiser vos coûts</li>
                                </ol>
                            </div>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0 0 10px; color: #6b7280; font-size: 13px; text-align: center;">
                                Besoin d'aide ? Consultez notre documentation ou contactez le support.
                            </p>
                            <p style="margin: 0; color: #9ca3af; font-size: 12px; text-align: center; line-height: 1.5;">
                                © 2025 CloudWaste. Tous droits réservés.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def get_welcome_email_text(full_name: str) -> str:
    """
    Get plain text version for welcome email.

    Args:
        full_name: User's full name

    Returns:
        Plain text email content
    """
    app_url = settings.FRONTEND_URL

    return f"""
🎉 Félicitations !

Votre compte est activé, {full_name} !

Votre adresse email a été vérifiée avec succès. Vous pouvez maintenant accéder à toutes les fonctionnalités de CloudWaste :

📊 Scans automatiques
   Détection des ressources orphelines AWS et Azure

💰 Économies identifiées
   Estimation précise des coûts gaspillés

🤖 Assistant IA FinOps
   Conseils personnalisés par Claude AI

🚀 Accédez à CloudWaste : {app_url}/auth/login

🎯 Prochaines étapes :
1. Connectez votre compte AWS ou Azure
2. Lancez votre premier scan
3. Découvrez vos économies potentielles
4. Discutez avec l'assistant IA pour optimiser vos coûts

---
Besoin d'aide ? Consultez notre documentation ou contactez le support.
© 2025 CloudWaste. Tous droits réservés.
"""


def send_welcome_email(email: str, full_name: str) -> bool:
    """
    Send welcome email to user after email verification.

    Args:
        email: User email address
        full_name: User's full name

    Returns:
        True if email sent successfully, False otherwise
    """
    html_content = get_welcome_email_html(full_name)
    text_content = get_welcome_email_text(full_name)

    return send_email(
        to_email=email,
        subject="🎉 Bienvenue sur CloudWaste - Votre compte est activé !",
        html_content=html_content,
        text_content=text_content,
    )
