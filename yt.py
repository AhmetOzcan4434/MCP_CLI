from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from mcp.server.fastmcp import FastMCP

def extract_video_id(url_or_id):
    """Extract video ID if a URL is given, otherwise return the ID as-is."""
    if "youtube.com" in url_or_id or "youtu.be" in url_or_id:
        query = urlparse(url_or_id).query
        return parse_qs(query).get('v', [None])[0]
    return url_or_id 

mcp = FastMCP("yt")

@mcp.tool()
def get_transcript(video_id: str) -> str:
    """Get transcript for a given YouTube video ID or URL show full transcript to user.
    Args:
        video_id: The video ID or full URL.
    Returns:
        str: full Transcript text.
    """
    video_id = extract_video_id(video_id)
    if not video_id:
        return "Invalid YouTube URL or ID."

    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'en-GB'])
        transcript_text = " ".join([line['text'] for line in transcript_list])
        return transcript_text
    except Exception as e:
        return f"Transcript retrieval failed: {
            str(e)}"
    
if __name__ == "__main__":
    mcp.run(transport="stdio")
