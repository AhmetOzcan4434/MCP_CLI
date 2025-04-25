import asyncio
from contextlib import AsyncExitStack
import json
import os
import sys
from typing import Optional
import base64
from pathlib import Path
import traceback
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, stdio_client
from together import Together

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        load_dotenv()
        self.client = Together(api_key=os.getenv('TOGETHER_API'))
        self.messages = [
            {"role": "system", "content": "Sen bir yardımcı asistansın ve gerektiğinde araçları kullanabilirsin."}
        ]

    async def connect_to_server(self, server_script_path: str):
        if not (server_script_path.endswith('.py') or server_script_path.endswith('.js')):
            raise ValueError("Sunucu scripti .py ya da .js dosyası olmalı")

        command = "python" if server_script_path.endswith('.py') else "node"
        server_params = StdioServerParameters(command=command, args=[server_script_path], env=None)

        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

            await self.session.initialize()
        except Exception as e:
            await self.cleanup()
            raise RuntimeError(f"Sunucuya bağlanırken hata oluştu: {e}")

    async def process_query(self, query: str) -> str:
        if not self.session:
            raise RuntimeError("İşlem yapmadan önce connect_to_server metodunu çağırmalısınız.")
            
        self.messages.append({"role": "user", "content": query})

        try:
            response = await self.session.list_tools()
            available_tools = [{
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            } for tool in response.tools]

            response = self.client.chat.completions.create(
                model="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
                max_tokens=5000,
                messages=self.messages,
                tools=available_tools
            )

            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)

            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    result = await self.session.call_tool(tool_name, tool_args)

                    self.messages.append({
                        "role": "assistant",
                        "tool_calls": [tool_call.model_dump()]
                    })

                    tool_result_content = result.content
                    try:
                        if isinstance(tool_result_content, list):
                            tool_result_content = "\n".join(
                                [str(item.text) if hasattr(item, "text") else str(item) for item in tool_result_content])
                        else:
                            tool_result_content = str(tool_result_content)
                    except Exception as e:
                        tool_result_content = f"[Araç yanıtı işlenirken hata: {e}]"

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result_content
                    })

                response = self.client.chat.completions.create(
                    model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
                    max_tokens=2000,
                    messages=self.messages
                )
                final_response = response.choices[0].message.content or "[Boş yanıt]"
                self.messages.append({"role": "assistant", "content": final_response})
                return final_response

            else:
                content = message.content or "[Boş yanıt]"
                self.messages.append({"role": "assistant", "content": content})
                return content

        except Exception as e:
            error_msg = f"[Hata: {e}]"
            self.messages.append({"role": "assistant", "content": error_msg})
            return error_msg

    async def process_image_query(self, image_input: str, prompt: str) -> str:
        """
        Resim verisi içeren bir sorguyu işler.
        
        Args:
            image_input: Görsel verisi (data URL, base64 veya dosya yolu)
            prompt: Resim hakkında sorgu
            
        Returns:
            LLM'den gelen yanıt
        """
        try:
            # Data URL kontrolü
            if image_input.startswith("data:image"):
                image_url = image_input
            # Dosya yolu kontrolü
            elif os.path.exists(image_input):
                image_path = Path(image_input)
                with open(image_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    image_url = f"data:image/{image_path.suffix[1:]};base64,{base64_image}"
            # Base64 formatında veri kontrolü
            else:
                try:
                    # Base64 verisini decode etmeyi dene
                    base64.b64decode(image_input)
                    image_url = f"data:image/png;base64,{image_input}"
                except:
                    return f"[Hata: Geçersiz görsel verisi veya dosya yolu: {image_input[:30]}...]"
            
            response = self.client.chat.completions.create(
                model="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }]
            )

            message = response.choices[0].message
            return message.content or "[Boş yanıt]"
        except Exception as e:
            error_detail = traceback.format_exc()
            return f"[Görsel işleme hatası: {str(e)}]\n\nDetay: {error_detail}"
    
    def reset_conversation(self):
        """Sohbet geçmişini sıfırlar, sadece sistem mesajını korur"""
        system_message = next((msg for msg in self.messages if msg["role"] == "system"), None)
        self.messages = [system_message] if system_message else [
            {"role": "system", "content": "Sen bir yardımcı asistansın ve gerektiğinde araçları kullanabilirsin."}
        ]
        return "Sohbet geçmişi temizlendi."

    async def cleanup(self):
        """Kaynakları temizle"""
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            print(f"Temizleme sırasında hata: {e}")
        finally:
            self.session = None


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python d1.py <sunucu_script_yolu>")
        sys.exit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    client = MCPClient()
    
    try:
        # Sunucuya bağlan
        print(f"Sunucuya bağlanılıyor: {sys.argv[1]}")
        loop.run_until_complete(client.connect_to_server(sys.argv[1]))
        print("Sunucu bağlantısı başarılı")
        
        # GUI modülünü importla
        from gui import GUI
        
        # GUI'yi başlat
        gui = GUI(client, loop)
        gui.start()
    except Exception as e:
        print(f"Hata: {e}")
        traceback.print_exc()
    finally:
        print("Kaynaklar temizleniyor...")
        loop.run_until_complete(client.cleanup())
        print("Program sonlandı")


if __name__ == "__main__":
    main()