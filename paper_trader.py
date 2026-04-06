import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
from nifty_100_stocks import NIFTY_100_STOCKS

class PaperTrader:
    """
    Paper Trading Simulator with Smart Position Sizing
    """
    
    def __init__(self, initial_capital=100000, email='kuberavpaul@gmail.com'):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.email = email
        self.positions = {}  # {stock: {qty, entry_price, entry_date, amount}}
        self.closed_trades = []  # History of closed trades
        self.portfolio_history = []  # Daily snapshots
        self.trades_log = []  # All trades
        
        # Use NIFTY 100 stocks
        self.nifty_stocks = NIFTY_100_STOCKS
        
        self.load_portfolio()
    
    def load_portfolio(self):
        """Load existing portfolio from file"""
        if os.path.exists('portfolio.json'):
            with open('portfolio.json', 'r') as f:
                data = json.load(f)
                self.positions = data.get('positions', {})
                self.cash = data.get('cash', self.initial_capital)
                self.closed_trades = data.get('closed_trades', [])
                self.trades_log = data.get('trades_log', [])
    
    def save_portfolio(self):
        """Save portfolio to file"""
        data = {
            'positions': self.positions,
            'cash': self.cash,
            'closed_trades': self.closed_trades,
            'trades_log': self.trades_log,
            'last_updated': datetime.now().isoformat()
        }
        with open('portfolio.json', 'w') as f:
            json.dump(data, f, indent=2)
    
    def calculate_indicators(self, data):
        """Calculate technical indicators"""
        if data.empty or len(data) < 200:
            return None
        
        data['SMA_50'] = data['Close'].rolling(50).mean()
        data['SMA_200'] = data['Close'].rolling(200).mean()
        data['EMA_12'] = data['Close'].ewm(span=12, adjust=False).mean()
        data['EMA_26'] = data['Close'].ewm(span=26, adjust=False).mean()
        
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        data['MACD'] = data['EMA_12'] - data['EMA_26']
        data['MACD_signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
        data['Volume_MA'] = data['Volume'].rolling(20).mean()
        
        return data
    
    def get_signal_strength(self, stock, data):
        """
        Calculate signal strength (0-3)
        Returns: (score, signal_type, target, stop_loss)
        """
        try:
            current = data.iloc[-1]
            
            sma50 = float(current['SMA_50']) if not pd.isna(current['SMA_50']) else None
            sma200 = float(current['SMA_200']) if not pd.isna(current['SMA_200']) else None
            rsi = float(current['RSI']) if not pd.isna(current['RSI']) else None
            macd = float(current['MACD']) if not pd.isna(current['MACD']) else None
            signal = float(current['MACD_signal']) if not pd.isna(current['MACD_signal']) else None
            volume = float(current['Volume']) if not pd.isna(current['Volume']) else None
            vol_ma = float(current['Volume_MA']) if not pd.isna(current['Volume_MA']) else None
            price = float(current['Close']) if not pd.isna(current['Close']) else None
            
            # Check for None values
            if sma50 is None or sma200 is None or rsi is None or volume is None or vol_ma is None or price is None:
                return 0, "HOLD", 0, 0
        except:
            return 0, "HOLD", 0, 0
        
        score = 0
        
        # Condition 1: SMA 50 > SMA 200
        if sma50 > sma200:
            score += 1
        
        # Condition 2: RSI 40-70
        if 40 <= rsi <= 70:
            score += 1
        
        # Condition 3: Volume > 90% of average
        if volume > (vol_ma * 0.9):
            score += 1
        
        # Calculate targets and stop loss
        target = price * 1.08  # 8% take profit
        stop_loss = price * 0.97  # 3% stop loss
        
        if score == 3:
            signal_type = "STRONG_BUY"
        elif score == 2:
            signal_type = "BUY"
        else:
            signal_type = "HOLD"
        
        return score, signal_type, target, stop_loss
    
    def scan_stocks(self):
        """Scan all NIFTY 50 stocks for buy signals"""
        signals = []
        
        print(f"\n{'='*80}")
        print(f"📊 SCANNING {len(self.nifty_stocks)} NIFTY 100 STOCKS | {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        for i, stock in enumerate(self.nifty_stocks, 1):
            try:
                # Skip if already in position
                if stock in self.positions:
                    continue
                
                print(f"[{i:2d}/{len(self.nifty_stocks)}] Scanning {stock}...", end=" ")
                
                # Download data
                end_date = datetime.now()
                start_date = end_date - timedelta(days=365)
                data = yf.download(stock, start=start_date, end=end_date, progress=False)
                
                if data is None or data.empty or len(data) < 200:
                    print("❌ Insufficient data")
                    continue
                
                # Calculate indicators
                try:
                    data = self.calculate_indicators(data)
                except Exception as calc_err:
                    print(f"❌ Error: {str(calc_err)[:30]}")
                    continue
                
                if data is None:
                    print("❌ Error calculating indicators")
                    continue
                
                # Get signal
                try:
                    score, signal_type, target, stop_loss = self.get_signal_strength(stock, data)
                    price = data['Close'].iloc[-1].item() if hasattr(data['Close'].iloc[-1], 'item') else float(data['Close'].iloc[-1])
                except Exception as sig_err:
                    print(f"❌ Error: {str(sig_err)[:30]}")
                    continue
                
                if score >= 2:  # BUY or STRONG_BUY
                    signals.append({
                        'stock': stock,
                        'price': price,
                        'score': score,
                        'signal': signal_type,
                        'target': target,
                        'stop_loss': stop_loss
                    })
                    print(f"✅ {signal_type} (Score: {score}/3) @ ₹{price:.2f}")
                else:
                    print(f"⏸️  HOLD (Score: {score}/3)")
                
                time.sleep(0.3)  # Rate limiting
            
            except Exception as e:
                print(f"❌ Error: {str(e)[:30]}")
        
        return sorted(signals, key=lambda x: x['score'], reverse=True)
    
    def position_size_calculator(self, score, price):
        """
        Smart position sizing based on signal strength
        Score 3 (STRONG_BUY) → Larger position
        Score 2 (BUY) → Smaller position
        """
        available = self.cash
        
        if score == 3:
            # STRONG_BUY: 8% of cash
            allocation = available * 0.08
        elif score == 2:
            # BUY: 4% of cash
            allocation = available * 0.04
        else:
            return 0, 0
        
        qty = int(allocation / price)
        amount = qty * price
        
        return qty, amount
    
    def place_order(self, stock, price, score):
        """Place a BUY order"""
        qty, amount = self.position_size_calculator(score, price)
        
        if qty == 0 or amount > self.cash:
            return False
        
        # Calculate target and stop loss
        target = price * 1.08
        stop_loss = price * 0.97
        
        self.positions[stock] = {
            'qty': qty,
            'entry_price': price,
            'entry_date': datetime.now().isoformat(),
            'amount': amount,
            'target': target,
            'stop_loss': stop_loss,
            'score': score
        }
        
        self.cash -= amount
        
        trade = {
            'timestamp': datetime.now().isoformat(),
            'action': 'BUY',
            'stock': stock,
            'qty': qty,
            'price': price,
            'amount': amount,
            'score': score
        }
        self.trades_log.append(trade)
        
        print(f"  ✅ BOUGHT {qty} units of {stock} @ ₹{price:.2f} | Amount: ₹{amount:.0f}")
        
        return True
    
    def update_positions(self):
        """Update all open positions and close if SL/TP hit"""
        closed_today = []
        
        for stock, position in list(self.positions.items()):
            try:
                # Get current price
                data = yf.download(stock, progress=False)
                current_price = data['Close'].iloc[-1]
                
                entry_price = position['entry_price']
                qty = position['qty']
                pnl = (current_price - entry_price) * qty
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                
                # Check stop loss
                if current_price <= position['stop_loss']:
                    exit_amount = current_price * qty
                    self.cash += exit_amount
                    
                    closed_trade = {
                        'stock': stock,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'qty': qty,
                        'entry_date': position['entry_date'],
                        'exit_date': datetime.now().isoformat(),
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'reason': 'STOP_LOSS'
                    }
                    self.closed_trades.append(closed_trade)
                    del self.positions[stock]
                    closed_today.append(closed_trade)
                    print(f"  🔴 STOP LOSS: {stock} @ ₹{current_price:.2f} | Loss: ₹{pnl:.0f} ({pnl_pct:.2f}%)")
                
                # Check take profit
                elif current_price >= position['target']:
                    exit_amount = current_price * qty
                    self.cash += exit_amount
                    
                    closed_trade = {
                        'stock': stock,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'qty': qty,
                        'entry_date': position['entry_date'],
                        'exit_date': datetime.now().isoformat(),
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'reason': 'TAKE_PROFIT'
                    }
                    self.closed_trades.append(closed_trade)
                    del self.positions[stock]
                    closed_today.append(closed_trade)
                    print(f"  🟢 TAKE PROFIT: {stock} @ ₹{current_price:.2f} | Profit: ₹{pnl:.0f} ({pnl_pct:.2f}%)")
                
                time.sleep(0.2)
            
            except Exception as e:
                pass
        
        return closed_today
    
    def get_portfolio_value(self):
        """Calculate current portfolio value"""
        value = self.cash
        
        for stock, position in self.positions.items():
            try:
                data = yf.download(stock, progress=False)
                current_price = data['Close'].iloc[-1]
                value += current_price * position['qty']
            except:
                pass
        
        return value
    
    def send_email_alert(self, subject, body):
        """Send email alert via Gmail"""
        try:
            msg = MIMEMultipart()
            msg['From'] = 'kuberavpaul@gmail.com'
            msg['To'] = self.email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html'))
            
            # Gmail SMTP configuration
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login('kuberavpaul@gmail.com', 'gkcuzhfteghwcjhw')
            server.send_message(msg)
            server.quit()
            
            print(f"✅ Email sent to {self.email}")
        
        except Exception as e:
            print(f"❌ Error sending email: {str(e)}")
            # Fallback: save to file if email fails
            try:
                with open('email_log.txt', 'a') as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"TO: {self.email}\n")
                    f.write(f"SUBJECT: {subject}\n")
                    f.write(f"TIME: {datetime.now()}\n")
                    f.write(f"{'='*80}\n")
                    f.write(body)
                    f.write(f"\n{'='*80}\n")
            except:
                pass
    
    def generate_email_report(self):
        """Generate daily email report"""
        portfolio_value = self.get_portfolio_value()
        total_pnl = portfolio_value - self.initial_capital
        total_pnl_pct = (total_pnl / self.initial_capital) * 100
        
        html = f"""
        <html>
        <body style="font-family: Arial; background: #f5f5f5; padding: 20px;">
        
        <div style="background: white; padding: 20px; border-radius: 8px; max-width: 800px; margin: 0 auto;">
            
            <h2 style="color: #333; text-align: center;">📊 PAPER TRADING REPORT</h2>
            <p style="text-align: center; color: #666; font-size: 12px;">{datetime.now().strftime('%d-%b-%Y %H:%M:%S')}</p>
            
            <hr style="border: none; border-top: 2px solid #ddd; margin: 20px 0;">
            
            <h3 style="color: #333; margin-bottom: 15px;">💰 Portfolio Summary</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #f9f9f9;">
                    <td style="padding: 10px; border: 1px solid #ddd;">Initial Capital</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;"><b>₹{self.initial_capital:,.0f}</b></td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;">Current Value</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;"><b style="color: {'green' if total_pnl >= 0 else 'red'};">₹{portfolio_value:,.0f}</b></td>
                </tr>
                <tr style="background: #f9f9f9;">
                    <td style="padding: 10px; border: 1px solid #ddd;">Total P&L</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;"><b style="color: {'green' if total_pnl >= 0 else 'red'};">₹{total_pnl:,.0f} ({total_pnl_pct:+.2f}%)</b></td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;">Cash Available</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;"><b>₹{self.cash:,.0f}</b></td>
                </tr>
            </table>
            
            <h3 style="color: #333; margin-top: 20px; margin-bottom: 15px;">📈 Open Positions ({len(self.positions)})</h3>
            {self._generate_positions_table()}
            
            <h3 style="color: #333; margin-top: 20px; margin-bottom: 15px;">✅ Closed Trades (Last 5)</h3>
            {self._generate_closed_trades_table()}
            
            <hr style="border: none; border-top: 2px solid #ddd; margin: 20px 0;">
            <p style="text-align: center; color: #999; font-size: 12px;">
                This is an automated paper trading report. No real money was invested.
            </p>
        </div>
        
        </body>
        </html>
        """
        
        subject = f"📊 Paper Trading Report - {datetime.now().strftime('%d-%b-%Y')}"
        self.send_email_alert(subject, html)
    
    def _generate_positions_table(self):
        """Generate HTML table for open positions"""
        if not self.positions:
            return "<p style='color: #999;'>No open positions</p>"
        
        rows = ""
        for stock, pos in self.positions.items():
            try:
                data = yf.download(stock, progress=False)
                current_price = data['Close'].iloc[-1]
                pnl = (current_price - pos['entry_price']) * pos['qty']
                pnl_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
                
                color = 'green' if pnl >= 0 else 'red'
                
                rows += f"""
                <tr style="{'background: #f9f9f9;' if self.nifty_50_stocks.index(stock) % 2 == 0 else ''}">
                    <td style="padding: 10px; border: 1px solid #ddd;"><b>{stock}</b></td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">₹{pos['entry_price']:.2f}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">₹{current_price:.2f}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{pos['qty']}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right; color: {color};"><b>₹{pnl:.0f} ({pnl_pct:+.2f}%)</b></td>
                </tr>
                """
                time.sleep(0.1)
            except:
                pass
        
        return f"""
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background: #333; color: white;">
                <th style="padding: 10px; text-align: left;">Stock</th>
                <th style="padding: 10px; text-align: right;">Entry</th>
                <th style="padding: 10px; text-align: right;">Current</th>
                <th style="padding: 10px; text-align: right;">Qty</th>
                <th style="padding: 10px; text-align: right;">P&L</th>
            </tr>
            {rows}
        </table>
        """
    
    def _generate_closed_trades_table(self):
        """Generate HTML table for closed trades"""
        if not self.closed_trades:
            return "<p style='color: #999;'>No closed trades yet</p>"
        
        recent_trades = self.closed_trades[-5:]
        rows = ""
        
        for trade in reversed(recent_trades):
            color = 'green' if trade['pnl'] >= 0 else 'red'
            rows += f"""
            <tr style="{'background: #f9f9f9;' if self.closed_trades.index(trade) % 2 == 0 else ''}">
                <td style="padding: 10px; border: 1px solid #ddd;"><b>{trade['stock']}</b></td>
                <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">₹{trade['entry_price']:.2f}</td>
                <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">₹{trade['exit_price']:.2f}</td>
                <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{trade['reason']}</td>
                <td style="padding: 10px; border: 1px solid #ddd; text-align: right; color: {color};"><b>₹{trade['pnl']:.0f} ({trade['pnl_pct']:+.2f}%)</b></td>
            </tr>
            """
        
        return f"""
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background: #333; color: white;">
                <th style="padding: 10px; text-align: left;">Stock</th>
                <th style="padding: 10px; text-align: right;">Entry</th>
                <th style="padding: 10px; text-align: right;">Exit</th>
                <th style="padding: 10px; text-align: right;">Reason</th>
                <th style="padding: 10px; text-align: right;">P&L</th>
            </tr>
            {rows}
        </table>
        """
    
    def run_daily(self):
        """Run daily trading cycle"""
        print(f"\n\n{'#'*80}")
        print(f"# PAPER TRADING SESSION - {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")
        print(f"{'#'*80}")
        
        # Scan for buy signals
        signals = self.scan_stocks()
        
        print(f"\n\n{'='*80}")
        print(f"📋 SIGNALS FOUND: {len(signals)}")
        print(f"{'='*80}\n")
        
        if signals:
            print(f"Placing orders...\n")
            for signal in signals[:10]:  # Max 10 new positions per day
                if self.cash > signal['price']:
                    self.place_order(signal['stock'], signal['price'], signal['score'])
                else:
                    print(f"  ⚠️  Insufficient cash for {signal['stock']}")
        
        # Update existing positions
        print(f"\n\n{'='*80}")
        print(f"📊 UPDATING POSITIONS")
        print(f"{'='*80}\n")
        
        closed = self.update_positions()
        
        # Save portfolio
        self.save_portfolio()
        
        # Generate report
        print(f"\n\n{'='*80}")
        print(f"📊 PORTFOLIO SUMMARY")
        print(f"{'='*80}\n")
        
        portfolio_value = self.get_portfolio_value()
        total_pnl = portfolio_value - self.initial_capital
        total_pnl_pct = (total_pnl / self.initial_capital) * 100
        
        print(f"Initial Capital    : ₹{self.initial_capital:,.0f}")
        print(f"Current Value      : ₹{portfolio_value:,.0f}")
        print(f"Total P&L          : ₹{total_pnl:,.0f} ({total_pnl_pct:+.2f}%)")
        print(f"Cash Available     : ₹{self.cash:,.0f}")
        print(f"Open Positions     : {len(self.positions)}")
        print(f"Closed Trades      : {len(self.closed_trades)}")
        
        # Send email
        self.generate_email_report()
        print(f"\n✅ Email report sent to {self.email}")

if __name__ == "__main__":
    trader = PaperTrader(initial_capital=100000, email='kuberavpaul@gmail.com')
    trader.run_daily()
