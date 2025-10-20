#!/usr/bin/env python3
"""Simple test server to demonstrate web panel functionality"""

import http.server
import json
import os
import socketserver
from datetime import datetime


class TestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_health_response()
        elif self.path.startswith("/lot/"):
            lot_id = self.path.split("/")[-1]
            self.serve_lot_page(lot_id)
        elif self.path == "/upload":
            self.serve_upload_page()
        elif self.path == "/":
            self.serve_index_page()
        elif self.path.startswith("/api/"):
            self.serve_mock_api()
        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        if self.path == "/upload-prices":
            self.handle_upload()
        else:
            self.send_error(404)

    def send_health_response(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"status": "healthy", "timestamp": datetime.now().isoformat()}
        self.wfile.write(json.dumps(response).encode())

    def serve_index_page(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>ZakupAI Test Panel</title></head>
        <body>
        <h1>ZakupAI Web Panel - Test Mode</h1>
        <p><a href="/lot/123456">Test Lot 123456</a></p>
        <p><a href="/upload">Upload Prices</a></p>
        <p><a href="/health">Health Check</a></p>
        </body>
        </html>
        """
        self.send_html_response(html)

    def serve_lot_page(self, lot_id):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Lot {lot_id} - ZakupAI</title></head>
        <body>
        <h1>Lot Analysis: {lot_id}</h1>
        <div id="lot-data">
        <h2>TL;DR</h2>
        <ul>
        <li>Лот: Тестовый лот #{lot_id}</li>
        <li>Цена: 1,500,000 тенге</li>
        <li>Заказчик: Тестовый заказчик</li>
        <li>Статус: Активный</li>
        </ul>

        <h2>Risk Assessment</h2>
        <p>Risk Score: 0.25 (Low Risk)</p>
        <p>Низкий риск: надежный заказчик, простые требования</p>

        <h2>Margin Analysis</h2>
        <p>Selling Price: 1,500,000 тенге</p>
        <p>Estimated Cost: 1,200,000 тенге</p>
        <p>Profit: 300,000 тенге (20%)</p>
        </div>
        </body>
        </html>
        """
        self.send_html_response(html)

    def serve_upload_page(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Upload Prices - ZakupAI</title></head>
        <body>
        <h1>Upload Price List</h1>
        <form action="/upload-prices" method="post" enctype="multipart/form-data">
        <p>
        <label>Source Name: <input type="text" name="source_name" placeholder="Kaspi.kz" required></label>
        </p>
        <p>
        <label>CSV File: <input type="file" name="file" accept=".csv,.xlsx" required></label>
        </p>
        <p>
        <button type="submit">Upload</button>
        </p>
        </form>

        <h2>Example CSV Format:</h2>
        <pre>sku,price,name,category
LAPTOP001,450000,Ноутбук Dell,Компьютеры
MOUSE001,5500,Мышь Logitech,Периферия</pre>
        </body>
        </html>
        """
        self.send_html_response(html)

    def serve_mock_api(self):
        # Mock API responses
        mock_data = {
            "/api/lot/123456/tldr": {
                "lot_id": "123456",
                "lines": [
                    "Лот: Тестовый лот #123456",
                    "Цена: 1,500,000 тенге",
                    "Заказчик: Тестовый заказчик",
                    "Статус: Активный",
                ],
                "ts": datetime.now().isoformat(),
            },
            "/api/lot/123456/risk": {
                "lot_id": "123456",
                "risk_score": 0.25,
                "explanation": "Низкий риск: надежный заказчик, простые требования",
            },
        }

        if self.path in mock_data:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(mock_data[self.path]).encode())
        else:
            self.send_error(404)

    def handle_upload(self):
        # Simple mock upload handler
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {
            "success": True,
            "total_rows": 5,
            "added": 3,
            "updated": 2,
            "skipped": 0,
            "filename": "test.csv",
            "source": "Test Upload",
        }
        self.wfile.write(json.dumps(response).encode())

    def send_html_response(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


if __name__ == "__main__":
    PORT = 8002
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    with socketserver.TCPServer(("", PORT), TestHandler) as httpd:
        print(f"Test server running at http://localhost:{PORT}/")
        print("Available endpoints:")
        print(f"  http://localhost:{PORT}/")
        print(f"  http://localhost:{PORT}/lot/123456")
        print(f"  http://localhost:{PORT}/upload")
        print(f"  http://localhost:{PORT}/health")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped")
