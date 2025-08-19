#!/usr/bin/env python3
"""
Password-Protected HTTP Server for Chatbot Report
Free alternative to Netlify password protection
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import base64
import os

class AuthHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.username = kwargs.pop('username', 'admin')
        self.password = kwargs.pop('password', 'ChatbotReport2025')
        super().__init__(*args, **kwargs)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_AUTH(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Chatbot Report - Enter Password"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        if self.headers.get('Authorization') == None:
            self.do_AUTH()
            return
        elif self.headers.get('Authorization') == 'Basic ' + str(
            base64.b64encode(f'{self.username}:{self.password}'.encode()).decode()
        ):
            SimpleHTTPRequestHandler.do_GET(self)
        else:
            self.do_AUTH()

def get_local_ip():
    """Get local IP address for network access"""
    import socket
    try:
        # Connect to a remote address to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "localhost"

def serve_with_auth(port=8000, username='admin', password='ChatbotReport2025'):
    """Start password-protected HTTP server"""
    handler = lambda *args, **kwargs: AuthHTTPRequestHandler(*args, username=username, password=password, **kwargs)
    
    try:
        httpd = HTTPServer(('0.0.0.0', port), handler)
        local_ip = get_local_ip()
        
        print("=" * 60)
        print("🔐 PASSWORD-PROTECTED CHATBOT REPORT SERVER")
        print("=" * 60)
        print(f"🌐 Local access: http://localhost:{port}")
        print(f"🌐 Network access: http://{local_ip}:{port}")
        print(f"👤 Username: {username}")
        print(f"🔑 Password: {password}")
        print("=" * 60)
        print("📋 Instructions:")
        print("1. Share the network URL with your team")
        print("2. Everyone needs the username and password")
        print("3. Press Ctrl+C to stop the server")
        print("=" * 60)
        
        httpd.serve_forever()
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"❌ Port {port} is already in use. Try a different port:")
            print(f"   python password_server.py --port {port + 1}")
        else:
            print(f"❌ Error starting server: {e}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Start password-protected HTTP server')
    parser.add_argument('--port', type=int, default=8000, help='Port to run server on (default: 8000)')
    parser.add_argument('--username', default='admin', help='Username for authentication (default: admin)')
    parser.add_argument('--password', default='ChatbotReport2025', help='Password for authentication')
    
    args = parser.parse_args()
    
    # Check if files exist
    if not os.path.exists('index.html'):
        print("❌ Error: index.html not found!")
        print("   Make sure you're running this script from the netlify-deploy folder")
        print("   Current directory:", os.getcwd())
        exit(1)
    
    serve_with_auth(port=args.port, username=args.username, password=args.password)
