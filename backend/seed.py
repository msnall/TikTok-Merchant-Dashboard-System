from app.db import Base, engine, SessionLocal
from app.models import Market, Product, Asset, Script, ContentTemplate, MixProject, MixProjectAsset, Tag, VideoWork

Base.metadata.create_all(engine)
db = SessionLocal()
if not db.query(Market).count():
    markets = [Market(name=n, language=l, country_code=c) for n,l,c in [("Indonesia","Bahasa Indonesia","ID"),("Thailand","Thai","TH"),("Vietnam","Vietnamese","VN"),("Malaysia","Malay","MY"),("Philippines","English","PH")]]
    db.add_all(markets); db.flush()
    products = [Product(name="Sunscreen", category="Beauty", selling_points="SPF50, lightweight, water resistant", description="Daily face sunscreen", market_id=markets[0].id), Product(name="Serum", category="Beauty", selling_points="Brightening and hydrating", market_id=markets[0].id), Product(name="Travel bottle", category="Lifestyle", selling_points="Leak-proof and reusable", market_id=markets[1].id)]
    db.add_all(products); db.flush()
    tags = [Tag(name=n, category=c) for n,c in [("pain point","structure"),("demo","purpose"),("before-after","visual"),("UGC","style"),("sunscreen","product")]]; db.add_all(tags); db.flush()
    db.add_all([Asset(name="Sunscreen texture close-up", asset_type="demo", source_platform="TikTok", market_id=markets[0].id, product_id=products[0].id, duration=5, tags_text="demo, sunscreen"), Asset(name="Outdoor skincare lifestyle", asset_type="lifestyle", source_platform="Douyin", market_id=markets[0].id, product_id=products[0].id, duration=8, tags_text="UGC, outdoor")])
    db.add_all([Script(title="Hot weather sunscreen pain point", script_type="pain_point", market_id=markets[0].id, product_id=products[0].id, hook="Still skipping sunscreen because it feels sticky?", body="This lightweight SPF50 absorbs in seconds and stays comfortable outdoors.", ending="No white cast, no heavy feeling.", cta="Tap to try it today.", duration=20, full_text="Still skipping sunscreen because it feels sticky? This lightweight SPF50 absorbs in seconds and stays comfortable outdoors. No white cast, no heavy feeling. Tap to try it today." )])
    db.add_all([ContentTemplate(name="Pain point to proof", template_type="pain_point", market_id=markets[0].id, product_id=products[0].id, recommended_duration=20, structure="0-3s Hook | 3-8s Product | 8-15s Demo | 15-18s Result | 18-20s CTA")])
    db.commit()
db.close()
print("Seed complete")

