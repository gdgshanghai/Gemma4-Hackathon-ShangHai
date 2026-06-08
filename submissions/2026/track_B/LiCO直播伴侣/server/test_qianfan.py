import asyncio
from gemma_api.services.search import search_baidu_ai

async def main():
    try:
        print("Starting search...")
        results = await search_baidu_ai("雪人三项", max_results=3)
        print("Results:")
        for r in results:
            print(r)
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
