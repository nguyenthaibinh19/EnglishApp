# main.py
import tkinter as tk
from quiz_app import VocabGuardApp

if __name__ == "__main__":
    root = tk.Tk()
    app = VocabGuardApp(root)
    root.mainloop()
