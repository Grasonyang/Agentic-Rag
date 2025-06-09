import aiohttp
import asyncio

from spider import parse_sitemap, web_crawler

async def main():
    # start_url = "https://money.udn.com/sitemap/staticmap/index"
    # collected_urls = []
    # async with aiohttp.ClientSession() as session:
    #     await parse_sitemap(session, start_url, collected_urls)

    # print(f"\n✅ 共收集 {len(collected_urls)} 筆內容頁面\n")
    
    # await web_crawler(collected_urls[:10])
    await web_crawler(["https://money.udn.com/money/story/123669/8793936"])

if __name__ == "__main__":
    asyncio.run(main())