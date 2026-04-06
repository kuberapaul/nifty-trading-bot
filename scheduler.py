"""
Paper Trading Scheduler for Render.com Free Tier
Runs continuously and checks for market open time (9:15 AM IST)
Keeps the service alive with a simple Flask health check
"""

import time
from datetime import datetime
from paper_trader import PaperTradingBot
import pytz
from flask import Flask
from threading import Thread

# Initialize Flask app for keeping service alive
app = Flask(__name__)

@app.route('/')
def home():
    return {
        'status': 'alive',
        'service': 'NIFTY Trading Bot Scheduler',
        'timestamp': datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
    }

@app.route('/health')
def health():
    return {'status': 'healthy'}, 200

class TradingScheduler:
    def __init__(self):
        self.bot = PaperTradingBot(
            initial_capital=100000,
            email='kuberavpaul@gmail.com'
        )
        self.ist = pytz.timezone('Asia/Kolkata')
        self.last_run_date = None
    
    def is_market_open_time(self):
        """Check if current time is 9:15 AM IST on weekday"""
        now = datetime.now(self.ist)
        
        # Check if weekday (Mon=0, Fri=4)
        if now.weekday() > 4:  # Saturday or Sunday
            return False
        
        # Check if time is 9:15 AM (with 2-minute window for safety)
        if now.hour == 9 and 14 <= now.minute <= 16:
            return True
        
        return False
    
    def run_trading(self):
        """Run trading session"""
        now = datetime.now(self.ist)
        
        # Only run once per day (even if scheduler runs multiple times in same minute)
        if self.last_run_date == now.date():
            return
        
        print(f"\n{'#'*80}")
        print(f"# 🤖 MARKET OPEN - STARTING TRADING SESSION")
        print(f"# Time: {now.strftime('%d-%b-%Y %H:%M:%S IST')}")
        print(f"{'#'*80}\n")
        
        try:
            self.bot.run_daily()
            self.last_run_date = now.date()
            print(f"\n{'#'*80}")
            print(f"# ✅ Trading session completed successfully")
            print(f"{'#'*80}\n")
        except Exception as e:
            print(f"\n❌ Error during trading session: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def start(self):
        """Start scheduler loop"""
        print(f"\n{'='*80}")
        print(f"🤖 NIFTY TRADING BOT SCHEDULER STARTED (Render Free Tier)")
        print(f"{'='*80}")
        print(f"Market Hours: 9:15 AM IST (Mon-Fri)")
        print(f"Email: kuberavpaul@gmail.com")
        print(f"Initial Capital: ₹100,000")
        print(f"Current Time: {datetime.now(self.ist).strftime('%d-%b-%Y %H:%M:%S IST')}")
        print(f"{'='*80}\n")
        
        # Keep checking for market open time
        while True:
            try:
                if self.is_market_open_time():
                    self.run_trading()
                
                # Check every 30 seconds
                time.sleep(30)
                
            except KeyboardInterrupt:
                print("\n✋ Scheduler stopped by user")
                break
            except Exception as e:
                print(f"⚠️  Error in scheduler loop: {str(e)}")
                time.sleep(60)

if __name__ == "__main__":
    scheduler = TradingScheduler()
    
    # Start Flask in background thread (keeps service alive on Render)
    flask_thread = Thread(
        target=lambda: app.run(host='0.0.0.0', port=int(5000), debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()
    print("✅ Flask health check service started on port 5000")
    
    # Start scheduler in main thread
    scheduler.start()

