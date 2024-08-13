import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import json
import os
import keyboard
from PIL import Image
from pystray import MenuItem as item
import pystray
import threading


class AbbreviationManagerApp:
    def __init__(self, master):
        self.master = master
        self.master.title("TEx")
        self.abbrev_dict = {}
        self.abbrev_file_path = "abbreviations.json"
        self.abbrev_hooks = {}
        self.editing_item_id = None
        self.tray_icon = None
        self.tray_thread = None

        self.create_widgets()
        self.load_abbreviations()

    def create_widgets(self):
        style = ttk.Style()
        style.theme_use("classic")
        style.configure("Treeview", background="#151515", foreground="white", fieldbackground="#151515", borderwidth=0, highlightthickness=0, rowheight=30)
        style.configure("Treeview.Heading", background="#151515", foreground="white", fieldbackground="#151515", relief="flat", font=('Poppins', 12), padding=[0, 15])

        style.map("Treeview", background=[("selected", "#353535")], foreground=[("selected", "white")])
        style.map("Treeview.Heading", background=[('pressed', '#121212'), ('active', '#353535')], foreground=[('pressed', 'white'), ('active', 'white')])

        Font = ctk.CTkFont(family="Poppins", size=12, weight="normal")

        mainFrame = ctk.CTkFrame(master=self.master, fg_color="#151515")
        mainFrame.pack(fill="both", expand=True)

        mainFrame.grid_rowconfigure(0, weight=1)
        mainFrame.grid_columnconfigure(1, weight=1)

        frame1 = ctk.CTkFrame(master=mainFrame, width=300, fg_color="#151515")
        frame1.grid(row=0, column=0, sticky="ns")

        frame2 = ctk.CTkFrame(master=mainFrame, fg_color="#151515")
        frame2.grid(row=0, column=1, sticky="nsew")

        self.nameEntry = ctk.CTkEntry(master=frame1, fg_color="transparent", border_color="white", placeholder_text="Name", placeholder_text_color="white", width=200, height=40, font=Font)
        self.nameEntry.grid(row=0, column=0, padx=20, pady=(65, 20))

        self.replacementEntry = ctk.CTkEntry(master=frame1, fg_color="transparent", border_color="white", placeholder_text="Replacement", placeholder_text_color="white", width=200, height=40, font=Font)
        self.replacementEntry.grid(row=1, column=0, padx=20, pady=(0, 20))

        self.button = ctk.CTkButton(master=frame1, text="Insert", fg_color="white", text_color="black", hover_color="#E8E8E8", width=200, height=40, font=Font, command=self.add_or_edit_abbreviation)
        self.button.grid(row=2, column=0, padx=20, pady=(0, 20))

        tree_scroll = ctk.CTkScrollbar(frame2)
        tree_scroll.pack(side="right", fill="y")

        self.tree = ttk.Treeview(frame2, yscrollcommand=tree_scroll.set)
        self.tree['columns'] = ("#", "Name", "Replacement", "Ignore", "Edit", "Delete")
        self.tree.column("#0", width=0, stretch=tk.NO)
        self.tree.column("#", anchor=tk.W, width=20)
        self.tree.column("Name", anchor=tk.W, width=80)
        self.tree.column("Replacement", anchor=tk.W, width=300)
        self.tree.column("Ignore", anchor=tk.W, width=50)
        self.tree.column("Edit", anchor=tk.W, width=20)
        self.tree.column("Delete", anchor=tk.W, width=20)

        self.tree.heading("#0", text="", anchor=tk.W)
        self.tree.heading("#", text="#", anchor=tk.W)
        self.tree.heading("Name", text="Name", anchor=tk.W)
        self.tree.heading("Replacement", text="Replacement", anchor=tk.W)
        self.tree.heading("Ignore", text="Ignore", anchor=tk.W)
        self.tree.heading("Edit", text="Edit", anchor=tk.W)
        self.tree.heading("Delete", text="Delete", anchor=tk.W)

        self.tree.pack(fill="both", expand=True, pady=(50, 0))
        tree_scroll.configure(command=self.tree.yview)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_item_click)
        
        self.button.bind("<Button-1>", self.on_button_click)

    def load_abbreviations(self):
        if os.path.exists(self.abbrev_file_path):
            try:
                with open(self.abbrev_file_path, 'r', encoding='utf-8') as f:
                    self.abbrev_dict = json.load(f)
                    for key, value in self.abbrev_dict.items():
                        if isinstance(value, str):
                            self.abbrev_dict[key] = {'replacement': value, 'ignored': False}
            except (json.JSONDecodeError, IOError) as e:
                tk.messagebox.showerror("Error", f"Failed to load abbreviations: {e}")
                self.abbrev_dict = {}
        else:
            self.abbrev_dict = {}

        self.update_abbreviation_listbox()
        self.apply_abbreviations()

    def save_abbreviations(self):
        try:
            with open(self.abbrev_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.abbrev_dict, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Failed to save abbreviations: {e}")

    def update_abbreviation_listbox(self):
        self.tree.delete(*self.tree.get_children())

        for idx, (source, data) in enumerate(self.abbrev_dict.items()):
            if isinstance(data, dict):
                item_id = self.tree.insert("", "end", values=(idx + 1, source, data['replacement'], "Unignored" if not data.get('ignored', False) else "Ignored"))
                self.tree.set(item_id, "Edit", "Edit")
                self.tree.set(item_id, "Delete", "Delete")

                if data.get('ignored', False):
                    self.tree.item(item_id, tags=("ignored",))
                else:
                    self.tree.item(item_id, tags=("unignored",))

        self.tree.tag_configure("ignored", foreground="#737373")
        self.tree.tag_configure("unignored", foreground="white")

    def apply_abbreviations(self):
        for hook in self.abbrev_hooks.values():
            keyboard.remove_word_listener(hook)
        self.abbrev_hooks.clear()

        for source, data in self.abbrev_dict.items():
            if not data.get('ignored', False):
                hook = keyboard.add_abbreviation(source, data['replacement'], timeout=5)
                self.abbrev_hooks[source] = hook

    def add_or_edit_abbreviation(self):
        source = self.nameEntry.get().strip()
        replacement = self.replacementEntry.get().strip()

        if source == "" or replacement == "":
            return

        if self.editing_item_id:
            original_source = self.tree.item(self.editing_item_id)['values'][1]
            if original_source in self.abbrev_dict:
                del self.abbrev_dict[original_source]
            self.abbrev_dict[source] = {'replacement': replacement, 'ignored': False}
            self.editing_item_id = None
            self.button.configure(text="Insert")
        else:
            self.abbrev_dict[source] = {'replacement': replacement, 'ignored': False}

        self.save_abbreviations()
        self.update_abbreviation_listbox()
        self.apply_abbreviations()

        self.nameEntry.delete(0, tk.END)
        self.replacementEntry.delete(0, tk.END)

    def edit_item(self, item_id):
        source = self.tree.item(item_id)['values'][1]
        data = self.abbrev_dict[source]

        self.nameEntry.delete(0, tk.END)
        self.nameEntry.insert(0, source)

        self.replacementEntry.delete(0, tk.END)
        self.replacementEntry.insert(0, data['replacement'])

        self.button.configure(text="Edit",fg_color="#55FF8E",hover_color="#55FF8E")
        self.nameEntry.configure(border_color="#55FF8E",placeholder_text_color="#55FF8E",text_color="#55FF8E")
        self.replacementEntry.configure(border_color="#55FF8E",placeholder_text_color="#55FF8E",text_color="#55FF8E")
        self.editing_item_id = item_id

    def delete_item(self, item_id):
        source = self.tree.item(item_id)['values'][1]
        del self.abbrev_dict[source]

        self.save_abbreviations()
        self.update_abbreviation_listbox()
        self.apply_abbreviations()

    def toggle_ignore_item(self, item_id):
        source = self.tree.item(item_id)['values'][1]
        if source in self.abbrev_dict:
            self.abbrev_dict[source]['ignored'] = not self.abbrev_dict[source].get('ignored', False)
            self.save_abbreviations()
            self.update_abbreviation_listbox()
            self.apply_abbreviations()

    def on_tree_item_click(self, event):
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)

        if item_id:
            if col == '#4':
                self.toggle_ignore_item(item_id)
            elif col == '#5':
                self.edit_item(item_id)
            elif col == '#6':
                self.delete_item(item_id)
    def on_button_click(self,event):
        self.button.configure(text="Insert",fg_color="white",hover_color="white")
        self.nameEntry.configure(border_color="white",placeholder_text_color="white",text_color="white")
        self.replacementEntry.configure(border_color="white",placeholder_text_color="white",text_color="white")

    def minimize_to_tray(self):
        self.hide_main_window()
        self.create_tray_icon()

    def hide_main_window(self):
        self.master.withdraw()

    def show_main_window(self, icon=None, item=None):
        self.master.deiconify()
        self.destroy_tray_icon()

    def quit_application(self, icon=None, item=None):
        self.destroy_tray_icon()
        self.master.quit()

    def create_tray_icon(self):
        if self.tray_icon:
            return

        image = Image.open("icon.ico")
        menu = (
            item('Show', self.show_main_window),
            item('Quit', self.quit_application)
        )
        self.tray_icon = pystray.Icon("name", image, "App Name", menu)
        self.tray_thread = threading.Thread(target=self.tray_icon.run)
        self.tray_thread.start()

    def destroy_tray_icon(self):
        if self.tray_icon:

            self.tray_icon.stop()
            self.tray_icon = None
            if self.tray_thread and threading.current_thread() != self.tray_thread:
                self.tray_thread.join()
            self.tray_thread = None

if __name__ == "__main__":
    root = ctk.CTk()
    root.iconbitmap('icon.ico')
    app = AbbreviationManagerApp(master=root)
    root.protocol("WM_DELETE_WINDOW", app.minimize_to_tray)
    root.geometry("1000x600")
    root.mainloop()