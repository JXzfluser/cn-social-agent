SAMPLE = """<?xml version="1.0"?>
<rss><channel>
<item><title>AI 工具盘点</title><link>https://sspai.com/x</link><description>desc</description></item>
</channel></rss>"""


def test_parse_rss_items():
    from cn_social_agent.tools.hotspots import parse_rss_items

    items = parse_rss_items(SAMPLE)
    assert len(items) == 1
    assert items[0]["title"] == "AI 工具盘点"
    assert items[0]["url"] == "https://sspai.com/x"
    assert items[0]["description"] == "desc"


def test_parse_rss_items_skips_empty_title():
    from cn_social_agent.tools.hotspots import parse_rss_items

    xml = """<?xml version="1.0"?>
<rss><channel>
<item><title></title><link>https://sspai.com/x</link></item>
<item><title>Valid</title><link>https://sspai.com/y</link></item>
</channel></rss>"""
    items = parse_rss_items(xml)
    assert len(items) == 1
    assert items[0]["title"] == "Valid"


def test_sspai_in_sources():
    from cn_social_agent.tools.hotspots import list_hotspot_sources

    ids = {s["id"] for s in list_hotspot_sources()}
    assert "sspai" in ids
