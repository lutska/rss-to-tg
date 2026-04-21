import feedparser

url = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"  # replace with your feed

feed = feedparser.parse(url)

top = feed.entries[0]

guid = top.get("id") or top.get("link")

print("TOP GUID:", guid)
print("TITLE:", top.get("title"))
print("LINK:", top.get("link"))