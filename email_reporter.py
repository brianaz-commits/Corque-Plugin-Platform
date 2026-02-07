"""
Email Reporter Tool
Sends formatted email reports with stock data
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List
from datetime import datetime


class EmailReporter:
    """Handles sending stock reports via email"""
    
    def __init__(self, smtp_server: str, smtp_port: int, 
                 sender_email: str, sender_password: str):
        """
        Args:
            smtp_server: SMTP server address (e.g., 'smtp.gmail.com')
            smtp_port: SMTP port (e.g., 587 for TLS)
            sender_email: Your email address
            sender_password: Your email password or app password
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
    
    def send_report(self, stock_data: Dict, recipient_email: str):
        """
        Send formatted stock report via email
        
        Args:
            stock_data: Dictionary containing stock information
            recipient_email: Email address to send report to
        """
        try:
            # Create email content
            subject = f"Stock Monitor Report - {stock_data['timestamp']}"
            html_body = self._format_html_report(stock_data)
            
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.sender_email
            message['To'] = recipient_email
            
            html_part = MIMEText(html_body, 'html')
            message.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            print(f"✓ Email report sent to {recipient_email}")
            
        except Exception as e:
            print(f"Failed to send email: {e}")
    
    def _format_html_report(self, stock_data: Dict) -> str:
        """Format stock data as HTML email"""
        stocks = stock_data.get('stocks', [])
        timestamp = stock_data.get('timestamp', 'N/A')
        
        # Build stock rows
        stock_rows = ""
        for stock in stocks:
            change_color = 'green' if stock['change'] >= 0 else 'red'
            arrow = '▲' if stock['change'] >= 0 else '▼'
            
            stock_rows += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #ddd;">
                    <strong>{stock['symbol']}</strong><br>
                    <small style="color: #666;">{stock['name']}</small>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #ddd; text-align: right;">
                    <strong>${stock['price']}</strong>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #ddd; text-align: right; color: {change_color};">
                    {arrow} ${abs(stock['change'])}<br>
                    <small>({stock['change_percent']:+.2f}%)</small>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #ddd; text-align: right;">
                    ${stock['low']} - ${stock['high']}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #ddd; text-align: right;">
                    {stock['volume']:,}
                </td>
            </tr>
            """
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background-color: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                h2 {{ color: #333; margin-top: 0; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th {{ background-color: #4CAF50; color: white; padding: 12px; text-align: left; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📊 Stock Monitor Report</h2>
                <p><strong>Report Time:</strong> {timestamp}</p>
                
                <table>
                    <thead>
                        <tr>
                            <th>Stock</th>
                            <th style="text-align: right;">Price</th>
                            <th style="text-align: right;">Change</th>
                            <th style="text-align: right;">Day Range</th>
                            <th style="text-align: right;">Volume</th>
                        </tr>
                    </thead>
                    <tbody>
                        {stock_rows}
                    </tbody>
                </table>
                
                <div class="footer">
                    <p>This is an automated report from your Stock Monitor Agent.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html


# Quick setup helper
def create_gmail_reporter(gmail_address: str, app_password: str) -> EmailReporter:
    """
    Create an EmailReporter configured for Gmail
    
    Note: You need to generate an App Password from your Google Account:
    https://myaccount.google.com/apppasswords
    """
    return EmailReporter(
        smtp_server='smtp.gmail.com',
        smtp_port=587,
        sender_email=gmail_address,
        sender_password=app_password
    )