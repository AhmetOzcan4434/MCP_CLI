import asyncio
import sys
from gui import GUI
from d1 import MCPClient

def main():
    if len(sys.argv) < 2:
        print("Kullanım: python main.py <sunucu_script_yolu>")
        sys.exit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    client = MCPClient()
    
    try:
        # Sunucuya bağlan
        print(f"Sunucuya bağlanılıyor: {sys.argv[1]}")
        loop.run_until_complete(client.connect_to_server(sys.argv[1]))
        print("Sunucu bağlantısı başarılı")
        
        # GUI'yi başlat
        gui = GUI(client, loop)
        gui.start()
    except Exception as e:
        print(f"Hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Kaynaklar temizleniyor...")
        loop.run_until_complete(client.cleanup())
        print("Program sonlandı")

if __name__ == "__main__":
    main()