"""
QUICK AUTHENTICATION - Auto Test Who You Are
=============================================
Automatically collects mouse data and identifies the user.
No need to select username - the system figures out who you are!

Usage:
    python quick_auth.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import csv
import random
from pathlib import Path
from typing import List
import numpy as np
import pandas as pd
from datetime import datetime

# Import backend modules
from feature_extractor import MouseFeatureExtractor
from real_time_auth import MouseAuthenticator


class QuickAuthApp:
    """Quick Authentication - Auto-detect who you are"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🔍 Quick Authentication - Who Are You?")
        self.root.geometry("900x700")
        self.root.configure(bg='#2c3e50')
        
        # Paths
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        
        # State
        self.is_collecting = False
        self.mouse_data = []
        self.dots = []
        self.start_time = None
        self.collection_duration = 30  # seconds
        self.selected_csv = None
        self.csv_users = []
        
        # Create UI
        self.create_ui()
        
        # Load available CSVs
        self.load_csv_files()
        
    def create_ui(self):
        """Create the user interface"""
        
        # Title
        title_frame = tk.Frame(self.root, bg='#34495e', pady=20)
        title_frame.pack(fill='x')
        
        title_label = tk.Label(
            title_frame,
            text="🔍 Quick Authentication",
            font=('Arial', 24, 'bold'),
            bg='#34495e',
            fg='white'
        )
        title_label.pack()
        
        subtitle = tk.Label(
            title_frame,
            text="Select a CSV dataset and we'll identify you from those users!",
            font=('Arial', 12),
            bg='#34495e',
            fg='#ecf0f1'
        )
        subtitle.pack(pady=(5, 0))
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # CSV Selection Frame
        csv_frame = tk.LabelFrame(
            main_frame,
            text="Step 1: Select CSV Dataset",
            font=('Arial', 12, 'bold'),
            bg='#34495e',
            fg='white',
            padx=15,
            pady=15
        )
        csv_frame.pack(fill='x', pady=(0, 10))
        
        csv_select_frame = tk.Frame(csv_frame, bg='#34495e')
        csv_select_frame.pack(fill='x')
        
        tk.Label(
            csv_select_frame,
            text="Choose Dataset:",
            font=('Arial', 11, 'bold'),
            bg='#34495e',
            fg='white'
        ).pack(side='left', padx=(0, 10))
        
        self.csv_combo = ttk.Combobox(
            csv_select_frame,
            font=('Arial', 11),
            state='readonly',
            width=40
        )
        self.csv_combo.pack(side='left', padx=5)
        self.csv_combo.bind('<<ComboboxSelected>>', self.on_csv_selected)
        
        self.csv_info_label = tk.Label(
            csv_frame,
            text="No CSV selected",
            font=('Arial', 10),
            bg='#34495e',
            fg='#ecf0f1'
        )
        self.csv_info_label.pack(pady=(10, 0))
        
        # Canvas for mouse movement
        canvas_frame = tk.LabelFrame(
            main_frame,
            text="Step 2: Move Your Mouse Here",
            font=('Arial', 12, 'bold'),
            bg='#34495e',
            fg='white',
            padx=10,
            pady=10
        )
        canvas_frame.pack(fill='both', expand=True)
        
        self.canvas = tk.Canvas(
            canvas_frame,
            bg='white',
            cursor='crosshair',
            highlightthickness=2,
            highlightbackground='#3498db'
        )
        self.canvas.pack(fill='both', expand=True)
        
        # Timer display
        self.timer_label = tk.Label(
            canvas_frame,
            text="",
            font=('Arial', 16, 'bold'),
            bg='#34495e',
            fg='#e74c3c'
        )
        self.timer_label.pack(pady=5)
        
        # Bind mouse events
        self.canvas.bind('<Motion>', self.on_mouse_move)
        self.canvas.bind('<Button-1>', self.on_mouse_click)
        
        # Control buttons
        button_frame = tk.Frame(main_frame, bg='#2c3e50')
        button_frame.pack(pady=15)
        
        self.start_btn = tk.Button(
            button_frame,
            text="▶ Start Collection & Auto-Authenticate",
            command=self.start_collection,
            font=('Arial', 14, 'bold'),
            bg='#27ae60',
            fg='white',
            padx=30,
            pady=15,
            cursor='hand2',
            relief='raised',
            bd=3,
            state='disabled'
        )
        self.start_btn.pack(side='left', padx=10)
        
        self.stop_btn = tk.Button(
            button_frame,
            text="⏹ Stop",
            command=self.stop_collection,
            font=('Arial', 14, 'bold'),
            bg='#e74c3c',
            fg='white',
            padx=30,
            pady=15,
            cursor='hand2',
            relief='raised',
            bd=3,
            state='disabled'
        )
        self.stop_btn.pack(side='left', padx=10)
        
        # Result display
        self.result_frame = tk.LabelFrame(
            main_frame,
            text="Authentication Result",
            font=('Arial', 12, 'bold'),
            bg='#34495e',
            fg='white',
            padx=15,
            pady=15
        )
        self.result_frame.pack(fill='x', pady=(10, 0))
        
        self.result_label = tk.Label(
            self.result_frame,
            text="Select a CSV dataset to begin...",
            font=('Arial', 14),
            bg='#34495e',
            fg='#ecf0f1',
            wraplength=800,
            justify='center'
        )
        self.result_label.pack()
        
    def load_csv_files(self):
        """Load available CSV files from data directory"""
        try:
            csv_files = list(self.data_dir.glob('*.csv'))
            
            if not csv_files:
                messagebox.showwarning(
                    "No CSV Files",
                    "No CSV files found in data/ directory!"
                )
                return
            
            # Create display names
            self.csv_options = {}
            for csv_path in csv_files:
                # Read CSV to get user count
                try:
                    df = pd.read_csv(csv_path)
                    if 'user' in df.columns:
                        users = sorted(df['user'].unique())
                        user_count = len(users)
                        display_name = f"{csv_path.name} ({user_count} users: {', '.join(users[:3])}{'...' if user_count > 3 else ''})"
                        self.csv_options[display_name] = {
                            'path': csv_path,
                            'users': users
                        }
                except Exception as e:
                    print(f"Error reading {csv_path.name}: {e}")
            
            # Populate dropdown
            if self.csv_options:
                self.csv_combo['values'] = list(self.csv_options.keys())
                print(f"✅ Loaded {len(self.csv_options)} CSV files")
            else:
                messagebox.showwarning(
                    "No Valid CSVs",
                    "No valid CSV files with 'user' column found!"
                )
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV files:\n{str(e)}")
    
    def on_csv_selected(self, event=None):
        """Handle CSV selection"""
        selected = self.csv_combo.get()
        if selected in self.csv_options:
            csv_info = self.csv_options[selected]
            self.selected_csv = csv_info['path']
            self.csv_users = csv_info['users']
            
            # Update info label
            user_list = ', '.join(self.csv_users)
            self.csv_info_label.config(
                text=f"✅ Ready! Users in dataset: {user_list}",
                fg='#2ecc71'
            )
            
            # Enable start button
            self.start_btn.config(state='normal')
            
            # Update result
            self.result_label.config(
                text=f"Ready to authenticate against {len(self.csv_users)} users!",
                fg='#3498db'
            )
            
            print(f"✅ Selected: {self.selected_csv.name}")
            print(f"   Users: {self.csv_users}")
    
    def load_users(self):
        """DEPRECATED - Not used anymore"""
        pass
    
    def start_collection(self):
        """Start collecting mouse data"""
        if self.is_collecting:
            return
            
        # Reset
        self.mouse_data = []
        self.dots = []
        self.canvas.delete('all')
        self.result_label.config(text="Collecting mouse movements...", fg='#f39c12')
        
        # Start
        self.is_collecting = True
        self.start_time = time.time()
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        # Spawn random dots
        self.spawn_dots()
        
        # Start timer countdown
        self.update_timer()
        
    def stop_collection(self):
        """Stop collecting and authenticate"""
        if not self.is_collecting:
            return
            
        self.is_collecting = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.timer_label.config(text="")
        
        # Check if we have enough data
        if len(self.mouse_data) < 50:
            messagebox.showwarning(
                "Insufficient Data",
                f"Only {len(self.mouse_data)} movements recorded.\nNeed at least 50 for authentication.\n\nTry again and move your mouse more!"
            )
            self.result_label.config(
                text="❌ Not enough data - try again!",
                fg='#e74c3c'
            )
            return
        
        # Authenticate against ALL users
        self.result_label.config(text="🔄 Analyzing your mouse behavior...", fg='#3498db')
        self.root.update()
        
        threading.Thread(target=self.authenticate_all_users, daemon=True).start()
    
    def authenticate_all_users(self):
        """Test authentication against all users in selected CSV"""
        try:
            if not self.selected_csv or not self.csv_users:
                self.root.after(0, self.show_error, "No CSV selected!")
                return
            
            # Save collected session
            temp_csv = self.base_dir / "temp_session.csv"
            with open(temp_csv, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['x', 'y', 'timestamp', 'event'])
                writer.writerows(self.mouse_data)
            
            # Extract features from collected session
            extractor = MouseFeatureExtractor()
            collected_features = extractor.extract_from_csv(str(temp_csv))
            
            if collected_features.empty:
                self.root.after(0, self.show_error, "Failed to extract features from your session!")
                temp_csv.unlink()
                return
            
            # Load CSV data and extract features for each user
            df = pd.read_csv(self.selected_csv)
            
            results = []
            for username in self.csv_users:
                try:
                    # Get this user's data
                    user_data = df[df['user'] == username]
                    
                    if len(user_data) < 10:
                        print(f"Skipping {username}: Not enough samples ({len(user_data)})")
                        continue
                    
                    # Calculate similarity (using simple Euclidean distance on feature means)
                    # Get feature columns (all except 'user')
                    feature_cols = [col for col in user_data.columns if col != 'user']
                    
                    # Calculate mean features for the user's training data
                    user_mean_features = user_data[feature_cols].mean()
                    
                    # Get collected session features (first row)
                    collected_mean = collected_features[feature_cols].iloc[0] if not collected_features.empty else pd.Series()
                    
                    # Calculate distance (lower = more similar)
                    distance = np.sqrt(((user_mean_features - collected_mean) ** 2).sum())
                    
                    # Convert distance to confidence (0-1, higher = more confident)
                    # Using inverse exponential: closer distance = higher confidence
                    confidence = np.exp(-distance / 100)  # Normalize by scaling factor
                    
                    results.append({
                        'username': username,
                        'confidence': confidence,
                        'distance': distance,
                        'is_genuine': confidence > 0.5  # Threshold
                    })
                    
                except Exception as e:
                    print(f"Error testing {username}: {e}")
            
            # Sort by confidence (highest first)
            results.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Display results
            self.root.after(0, self.display_results, results)
            
            # Clean up temp file
            temp_csv.unlink()
            
        except Exception as e:
            self.root.after(0, self.show_error, str(e))
    
    def display_results(self, results):
        """Display authentication results"""
        if not results:
            self.result_label.config(
                text="❌ No results - something went wrong!",
                fg='#e74c3c'
            )
            return
        
        # Get top match
        top_match = results[0]
        
        # Build result text
        if top_match['is_genuine']:
            # Strong match found
            result_text = f"✅ AUTHENTICATED!\n\n"
            result_text += f"You are: {top_match['username']}\n"
            result_text += f"Confidence: {top_match['confidence']*100:.1f}%"
            color = '#27ae60'
        else:
            # No strong match - show top 3 possibilities
            result_text = "❓ NO CLEAR MATCH FOUND\n\n"
            result_text += "Top 3 Closest Matches:\n"
            for i, r in enumerate(results[:3], 1):
                result_text += f"{i}. {r['username']} ({r['confidence']*100:.1f}%)\n"
            result_text += f"\nYou might be a new user not in the system."
            color = '#e74c3c'
        
        # Show detailed scores
        result_text += f"\n\nAll Scores:"
        for r in results[:5]:  # Top 5
            result_text += f"\n• {r['username']}: {r['confidence']*100:.1f}%"
        
        self.result_label.config(text=result_text, fg=color)
    
    def show_error(self, error_msg):
        """Show error message"""
        messagebox.showerror("Authentication Error", f"Error during authentication:\n{error_msg}")
        self.result_label.config(text="❌ Authentication failed - see error", fg='#e74c3c')
    
    def on_mouse_move(self, event):
        """Record mouse movement"""
        if self.is_collecting:
            timestamp = time.time()
            self.mouse_data.append([event.x, event.y, timestamp, 'move'])
    
    def on_mouse_click(self, event):
        """Record mouse click"""
        if self.is_collecting:
            timestamp = time.time()
            self.mouse_data.append([event.x, event.y, timestamp, 'click'])
            
            # Check if clicked on a dot
            for dot in self.dots[:]:
                coords = self.canvas.coords(dot)
                if coords:
                    x1, y1, x2, y2 = coords
                    if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                        self.canvas.delete(dot)
                        self.dots.remove(dot)
    
    def spawn_dots(self):
        """Spawn random dots for user to click"""
        if not self.is_collecting:
            return
        
        # Add new dot
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        if width > 1 and height > 1:
            x = random.randint(30, width - 30)
            y = random.randint(30, height - 30)
            
            dot = self.canvas.create_oval(
                x - 8, y - 8, x + 8, y + 8,
                fill='#3498db',
                outline='#2980b9',
                width=2,
                tags='dot'
            )
            self.dots.append(dot)
        
        # Schedule next dot (every 3-5 seconds)
        if self.is_collecting:
            delay = random.randint(3000, 5000)
            self.root.after(delay, self.spawn_dots)
    
    def update_timer(self):
        """Update countdown timer"""
        if not self.is_collecting:
            return
        
        elapsed = time.time() - self.start_time
        remaining = max(0, self.collection_duration - int(elapsed))
        
        self.timer_label.config(text=f"⏱️ Time Remaining: {remaining}s")
        
        if remaining <= 0:
            # Auto-stop and authenticate
            self.stop_collection()
        else:
            # Continue countdown
            self.root.after(1000, self.update_timer)


def main():
    """Launch the application"""
    root = tk.Tk()
    app = QuickAuthApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
