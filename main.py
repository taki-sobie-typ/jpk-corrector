import re
import xml.etree.ElementTree as ET
from pathlib import Path

import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk


def process_xml(xml_text: str):
    errors = []
    changes = 0

    try:
        ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return None, 0, [f"Blad skladni XML: {exc}"]

    ewid_match = re.search(
        r"(<tns:Ewidencja>)(.*?)(</tns:Ewidencja>)",
        xml_text,
        flags=re.DOTALL,
    )
    if not ewid_match:
        return None, 0, ["Nie znaleziono sekcji <tns:Ewidencja>."]

    ewid_body = ewid_match.group(2)

    sprzedaz_pattern = re.compile(
        r"(<tns:SprzedazWiersz>)(.*?)(</tns:SprzedazWiersz>)",
        flags=re.DOTALL,
    )

    if not sprzedaz_pattern.search(ewid_body):
        return None, 0, ["Nie znaleziono wierszy <tns:SprzedazWiersz> w ewidencji."]

    def update_sprzedaz(match: re.Match):
        nonlocal changes
        block = match.group(0)

        nr_pattern = re.compile(
            r"(<tns:NrKontrahenta>)(.*?)(</tns:NrKontrahenta>)",
            flags=re.DOTALL,
        )
        nr_match = nr_pattern.search(block)
        if not nr_match:
            errors.append("Brak <tns:NrKontrahenta> w jednym z wierszy sprzedazy.")
            return block

        nazwa_match = re.search(
            r"<tns:NazwaKontrahenta>(.*?)</tns:NazwaKontrahenta>",
            block,
            flags=re.DOTALL,
        )
        if not nazwa_match:
            errors.append("Brak <tns:NazwaKontrahenta> w jednym z wierszy sprzedazy.")
            return block

        nazwa_value = nazwa_match.group(1).strip()
        if not nazwa_value:
            errors.append("Pusta wartosc <tns:NazwaKontrahenta> w wierszu sprzedazy.")
            return block

        replacement = nazwa_value[:25]

        def replace_nr(nr_m: re.Match):
            nonlocal changes
            current_value = nr_m.group(2)
            if current_value.strip().lower() != "brak":
                return nr_m.group(0)

            leading_ws = re.match(r"^\s*", current_value).group(0)
            trailing_ws = re.search(r"\s*$", current_value).group(0)
            changes += 1
            return f"{nr_m.group(1)}{leading_ws}{replacement}{trailing_ws}{nr_m.group(3)}"

        return nr_pattern.sub(replace_nr, block)

    new_ewid_body = sprzedaz_pattern.sub(update_sprzedaz, ewid_body)
    new_xml = (
        xml_text[: ewid_match.start(2)]
        + new_ewid_body
        + xml_text[ewid_match.end(2) :]
    )

    return new_xml, changes, errors


def main():
    root = ctk.CTk()
    root.title("Korekta JPK")
    root.geometry("800x520")

    box_width = 760

    processed_bytes = None
    default_save_name = None

    container = ctk.CTkFrame(root, corner_radius=0, fg_color="transparent")
    container.pack(fill=tk.BOTH, expand=True)

    content = ctk.CTkFrame(container, corner_radius=0, fg_color="transparent")
    content.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)

    title = ctk.CTkLabel(
        content,
        text="Korekta pola NrKontrahenta",
        font=("TkDefaultFont", 16, "bold"),
        anchor="center",
    )
    title.pack(fill=tk.X, pady=(0, 12))

    buttons_frame = ctk.CTkFrame(content, corner_radius=0, fg_color="transparent")
    buttons_frame.pack(pady=(0, 12))

    file_info = ctk.CTkLabel(content, text="", anchor="w", wraplength=box_width)
    changes_info = ctk.CTkLabel(content, text="", anchor="w", wraplength=box_width)
    status_info = ctk.CTkLabel(content, text="", anchor="w", wraplength=box_width)
    error_info = ctk.CTkTextbox(
        content,
        height=120,
        width=box_width,
        wrap="word",
        text_color="red",
    )
    error_info.configure(state="disabled")

    def set_label(label: ctk.CTkLabel, value: str):
        label.configure(text=value)
        if value:
            label.pack(fill=tk.X, pady=2)
        else:
            label.pack_forget()

    def set_error_text(value: str):
        error_info.configure(state="normal")
        error_info.delete("1.0", tk.END)
        if value:
            error_info.insert(tk.END, value)
            error_info.pack(fill=tk.X, pady=6)
        else:
            error_info.pack_forget()
        error_info.configure(state="disabled")

    def set_status(text: str, color: str | None = None):
        status_info.configure(text=text, text_color=color or "grey")
        if text:
            status_info.pack(fill=tk.X, pady=2)
        else:
            status_info.pack_forget()

    def reset_result():
        nonlocal processed_bytes, default_save_name
        processed_bytes = None
        default_save_name = None
        set_label(file_info, "")
        set_label(changes_info, "")
        set_error_text("")
        set_status("")
        save_button.configure(state="disabled")

    def handle_pick_files():
        nonlocal processed_bytes, default_save_name
        reset_result()

        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("XML files", "*.xml")]
            )
        except Exception as exc:
            set_status(f"Blad dialogu wyboru pliku: {exc}", "red")
            return

        if not file_path:
            set_status("Nie wybrano pliku.")
            return

        file_name = Path(file_path).name
        set_label(file_info, f"Wybrany plik: {file_name}")

        try:
            raw_bytes = Path(file_path).read_bytes()
        except OSError as exc:
            set_status(f"Blad odczytu pliku: {exc}", "red")
            return

        try:
            xml_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            set_status(
                "Plik nie jest w kodowaniu UTF-8 lub zawiera bledne znaki.",
                "red",
            )
            return

        new_xml, changes, errors = process_xml(xml_text)
        if new_xml is None:
            set_status("Nie udalo sie przetworzyc pliku.", "red")
            set_error_text("\n".join(errors))
            return

        processed_bytes = new_xml.encode("utf-8")
        default_save_name = f"{Path(file_name).stem}_poprawiony.xml"

        set_label(changes_info, f"Liczba zmienionych pol: {changes}")
        set_error_text("\n".join(errors) if errors else "")

        set_status("Plik przetworzony. Mozesz zapisac wynik.", "green")
        save_button.configure(state="normal")

    def handle_save_file():
        nonlocal processed_bytes, default_save_name
        if not processed_bytes:
            set_status("Brak danych do zapisu.", "red")
            return

        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xml",
                filetypes=[("XML files", "*.xml")],
                initialfile=default_save_name,
            )
        except Exception as exc:
            set_status(f"Blad dialogu zapisu: {exc}", "red")
            return

        if not file_path:
            set_status("Zapis anulowany.")
            return

        try:
            Path(file_path).write_bytes(processed_bytes)
        except OSError as exc:
            set_status(f"Blad zapisu pliku: {exc}", "red")
            return

        set_status("Plik zapisany poprawnie.", "green")

    pick_button = ctk.CTkButton(
        buttons_frame,
        text="Wybierz plik XML",
        command=handle_pick_files,
        width=180,
    )
    save_button = ctk.CTkButton(
        buttons_frame,
        text="Zapisz",
        command=handle_save_file,
        width=140,
        state="disabled",
    )

    pick_button.pack(side=tk.LEFT, padx=6)
    save_button.pack(side=tk.LEFT, padx=6)

    root.mainloop()


if __name__ == "__main__":
    main()
