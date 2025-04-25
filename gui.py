# gui.py için düzeltmeler

import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import asyncio
from PIL import ImageGrab, Image
import io
import base64
import traceback

class GUI:
    def __init__(self, client, loop: asyncio.AbstractEventLoop):
        self.client = client
        self.loop = loop
        self.root = tk.Tk()
        self.root.title("MCP Chat GUI")
        
        # Ana çerçeve
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Sohbet alanı
        self.text_area = ScrolledText(main_frame, wrap=tk.WORD, height=25, width=80)
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 10))
        self.text_area.config(state=tk.DISABLED)
        
        # Giriş ve buton çerçevesi
        input_frame = tk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.entry = tk.Entry(input_frame, width=80)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", lambda event: self.send_query())
        # Pano yapıştırma desteği için yeni bind ekle
        self.entry.bind("<Control-v>", self._handle_paste)
        
        self.send_button = tk.Button(input_frame, text="Gönder", command=self.send_query)
        self.send_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Kısayol butonları çerçevesi
        shortcut_frame = tk.Frame(main_frame)
        shortcut_frame.pack(fill=tk.X, pady=5)
        
        # Kısayol butonları - düzeltilmiş liste
        self.shortcuts = [
            {"text": "Resim analizi", "command": "image:", "prefix": True},
            {"text": "Yardım", "command": "Kullanabileceğim araçları listeler misin?"},
            {"text": "Sohbeti Temizle", "command": lambda: self.clear_chat()},
            {"text": "Sohbeti Sıfırla", "command": lambda: self.reset_conversation()}
        ]
        
        for i, shortcut in enumerate(self.shortcuts[:2]):  # Sadece ilk 2 kısayol için butonlar
            btn = tk.Button(
                shortcut_frame, 
                text=shortcut["text"],
                command=lambda cmd=shortcut["command"], prefix=shortcut.get("prefix", False): 
                    self.insert_shortcut(cmd, prefix)
            )
            btn.pack(side=tk.LEFT, padx=(0 if i == 0 else 5, 0))
        
        # İşlem butonları çerçevesi
        action_frame = tk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=5)
        
        clear_button = tk.Button(action_frame, text="Sohbeti Temizle", command=self.clear_chat)
        clear_button.pack(side=tk.LEFT)
        
        reset_button = tk.Button(action_frame, text="Sohbeti Sıfırla", command=self.reset_conversation)
        reset_button.pack(side=tk.LEFT, padx=(5, 0))
        
        # Klavye kısayolları - düzeltilmiş
        self.root.bind("<Control-1>", lambda event: self.insert_shortcut(self.shortcuts[0]["command"], self.shortcuts[0].get("prefix", False)))
        self.root.bind("<Control-2>", lambda event: self.insert_shortcut(self.shortcuts[1]["command"], self.shortcuts[1].get("prefix", False)))
        self.root.bind("<Control-l>", lambda event: self.clear_chat())
        self.root.bind("<Control-r>", lambda event: self.reset_conversation())
        self.root.bind("<Control-i>", lambda event: self.insert_shortcut("image:", True))
        
        # Durum çubuğu
        self.status_var = tk.StringVar()
        self.status_var.set("Hazır")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Başlangıç mesajı
        self._append_text("MCP Chat sistemine hoş geldiniz! Yardım için 'Yardım' butonuna tıklayabilir veya Ctrl+2 kısayolunu kullanabilirsiniz.")

    def insert_shortcut(self, command, is_prefix=False):
        """Kısayolu giriş alanına ekler"""
        if callable(command):
            command()
            return
            
        if is_prefix:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, command)
            self.entry.focus_set()
        else:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, command)
            self.send_query()
    
    def clear_chat(self, event=None):
        """Sohbet alanını temizler"""
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)
        self.text_area.config(state=tk.DISABLED)
        self.status_var.set("Sohbet temizlendi")
        self._append_text("Sohbet alanı temizlendi. Sohbet geçmişi hala korunuyor.")
    
    def reset_conversation(self, event=None):
        """Sohbet geçmişini sıfırlar"""
        asyncio.ensure_future(self._reset_conversation(), loop=self.loop)
    
    async def _reset_conversation(self):
        result = self.client.reset_conversation()
        self.clear_chat()
        self._append_text(f"Sistem: {result}")
        self.status_var.set("Sohbet sıfırlandı")
        
    def start(self):
        self._integrate_asyncio()
        self.root.mainloop()

    def send_query(self):
        query = self.entry.get().strip()
        if not query:
            return

        self.entry.delete(0, tk.END)

        # "image:[Panodaki görsel]" özel durumunu kontrol et
        if query == "image:[Panodaki görsel]" or query == "image:":
            # Bu durumda panodan görsel işleme fonksiyonunu doğrudan çağır
            self._append_text(f"\nKullanıcı: [Panodan görsel yapıştırıldı]")
            asyncio.ensure_future(self._process_clipboard_image(), loop=self.loop)
        else:
            self._append_text(f"\nKullanıcı: {query}")
            self.status_var.set("İşleniyor...")

            if query.startswith("image:"):
                image_data = query[len("image:"):].strip()
                asyncio.ensure_future(self._handle_image_query(image_data), loop=self.loop)
            else:
                asyncio.ensure_future(self._handle_response(query), loop=self.loop)
    async def _handle_response(self, query: str):
        yanit = await self.client.process_query(query)
        self._append_text(f"Asistan: {yanit}")
        self.status_var.set("Hazır")

    async def _handle_image_query(self, image_data: str):
        """Görsel sorgularını işler. Base64 veya dosya yolu kabul eder."""
        self.status_var.set("Görsel analiz ediliyor...")
        yanit = None
        
        try:
            # Base64 verisi kontrolü
            if image_data.startswith("data:image"):
                # Zaten uygun formatta
                yanit = await self.client.process_image_query(image_data, "Bu görseli açıkla.")
            
            elif len(image_data) > 100:  # Muhtemelen base64 verisi
                try:
                    # Base64 decode kontrolü
                    base64.b64decode(image_data)
                    image_url = f"data:image/png;base64,{image_data}"
                    yanit = await self.client.process_image_query(image_url, "Bu görseli açıkla.")
                except Exception as e:
                    self._append_text(f"[Hata: Base64 verisi işlenemedi - {str(e)}]")
            
            # Boş veya kısa input - panoya bak veya dosya yolu olarak dene
            if not yanit:
                if not image_data.strip():
                    # Panodan alma denemesi
                    yanit = await self._process_clipboard_image()
                else:
                    # Dosya yolu olarak dene
                    try:
                        with open(image_data, "rb") as image_file:
                            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                            image_url = f"data:image/png;base64,{base64_image}"
                            yanit = await self.client.process_image_query(image_url, "Bu görseli açıkla.")
                    except FileNotFoundError:
                        yanit = f"[Hata: '{image_data}' dosyası bulunamadı]"
                    except Exception as e:
                        yanit = f"[Hata: Dosya okuma hatası - {str(e)}]"
        
        except Exception as e:
            yanit = f"[Görsel işleme hatası: {str(e)}]"
            self._append_text(f"[Hata detayı: {traceback.format_exc()}]")
        
        if yanit:
            self._append_text(f"Asistan: {yanit}")
        self.status_var.set("Hazır")

    """Panodan resmi işler ve sonucu ekrana yazdırır"""
    async def _process_clipboard_image(self):
        try:
            image = ImageGrab.grabclipboard()
            if isinstance(image, Image.Image):
                self.status_var.set("Panodaki görsel işleniyor...")
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
                image_url = f"data:image/png;base64,{base64_image}"

                # Doğrudan LLM'e gönder
                yanit = await self.client.process_image_query(image_url, "Bu görseli açıkla.")
                self._append_text(f"Asistan: {yanit}")
                self.status_var.set("Hazır")
                return yanit
            else:
                error_msg = "Panoda görsel bulunamadı. Lütfen önce bir görsel kopyalayın."
                self._append_text(f"Sistem: {error_msg}")
                self.status_var.set("Hazır")
                return error_msg
        except Exception as e:
            error_msg = f"[Pano görsel işleme hatası: {str(e)}]"
            self._append_text(f"Sistem: {error_msg}")
            self.status_var.set("Hazır")
            return error_msg


    def _append_text(self, text):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.config(state=tk.DISABLED)
        self.text_area.see(tk.END)

    def _integrate_asyncio(self, interval=100):
        def poll():
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()
            self.root.after(interval, poll)

        self.root.after(interval, poll)

    def _handle_paste(self, event):
        """Panodan yapıştırma işlemini yönetir"""
        if self.entry.get().startswith("image:"):
            try:
                image = ImageGrab.grabclipboard()
                if isinstance(image, Image.Image):
                    self.status_var.set("Görsel panodan yapıştırılıyor...")
                    # Önce görsel işleme işini başlat
                    asyncio.ensure_future(self._process_clipboard_image(), loop=self.loop)
                    # Görsel işleme başladığını belirt
                    self._append_text("\nKullanıcı: [Panodan görsel yapıştırıldı]")
                    # Entry'i temizle
                    self.entry.delete(0, tk.END)
                    return "break"  # Tkinter'in kendi yapıştırma işlemini engelle
                else:
                    self.status_var.set("Panoda görsel bulunamadı! Lütfen bir görsel kopyalayın.")
            except Exception as e:
                self.status_var.set(f"Yapıştırma hatası: {str(e)}")
                # Detaylı hata kaydı ekle
                print(f"Yapıştırma hatası: {traceback.format_exc()}")
        return None  # Tkinter'in varsayılan yapıştırma davranışına izin ver
    
    