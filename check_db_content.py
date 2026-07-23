import pymongo

try:
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client.shoehunter_ai
    
    print("Mevcut Koleksiyonlar:", db.list_collection_names())
    print("Toplam radar/ürün kaydı (watches):", db.watches.count_documents({}))
    print("Tarama geçmişi (mcp_audits):", db.mcp_audits.count_documents({}))
except Exception as e:
    print("Hata:", str(e))
