# --- 中略（import・env設定などは今までと同じ） ---

# --- DB構造に type カラム追加 ---
conn = sqlite3.connect("properties.db")
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS properties (
    id TEXT PRIMARY KEY,
    title TEXT,
    price INTEGER,
    size REAL,
    location TEXT,
    url TEXT,
    last_seen DATE,
    first_seen DATE,
    madori TEXT,
    chikunensu TEXT,
    type TEXT
)''')
try:
    c.execute("ALTER TABLE properties ADD COLUMN type TEXT")
except sqlite3.OperationalError:
    pass
conn.commit()

def generate_hash(title, price, size, location, prop_type):
    return hashlib.md5(f"{title}{price}{size}{location}{prop_type}".encode("utf-8")).hexdigest()

def fetch_properties(target_url, prop_type="house"):
    from selenium.webdriver.chrome.service import Service
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=ja-JP")
    options.add_argument("user-agent=Mozilla/5.0")

    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        print(f"🔄 {prop_type} URL: {target_url}")
        driver.get(target_url)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "search-result-item"))
        )
        time.sleep(2)

        results = driver.find_elements(By.CLASS_NAME, "search-result-item")
        print(f"📦 {prop_type} 検出物件数: {len(results)} 件")

        properties = []
        for item in results:
            try:
                title = item.find_element(By.CLASS_NAME, "head-content").text.strip()
                price_text = item.find_element(By.CLASS_NAME, "bukken-data-price").text.strip()
                price = int(price_text.replace("万円", "").replace(",", ""))
                location = item.find_element(By.CSS_SELECTOR, ".search-detail-head h3 small").text.strip()

                tds = item.find_elements(By.TAG_NAME, "td")
                if len(tds) < 5:
                    continue

                building_area_text = tds[3].text.strip()
                match = re.search(r"([0-9.]+)\s?(㎡|m2)", building_area_text)
                size = float(match.group(1)) if match else None
                if size is None:
                    continue

                try:
                    madori = item.find_element(By.CLASS_NAME, "bukken-data-madori").text.strip()
                except:
                    madori = "不明"

                chikunensu = "不明"
                try:
                    spans = item.find_elements(By.CSS_SELECTOR, ".columns span")
                    for span in spans:
                        text = span.text.strip()
                        if re.match(r"^(新築|築[0-9]+年|築浅)$", text):
                            chikunensu = text
                            break
                except:
                    pass

                link_elem = item.find_element(By.TAG_NAME, "a")
                link = link_elem.get_attribute("href")

                prop_id = generate_hash(title, price, size, location, prop_type)
                properties.append({
                    "id": prop_id,
                    "title": title,
                    "price": price,
                    "size": size,
                    "location": location,
                    "url": link,
                    "madori": madori,
                    "chikunensu": chikunensu,
                    "type": prop_type
                })

            except Exception as e:
                print(f"[{prop_type}] スキップ: {e}")
                continue

        return properties

    finally:
        driver.quit()

def update_database(new_props):
    today = datetime.now().date()
    changed_titles = []

    for prop in new_props:
        c.execute("SELECT price FROM properties WHERE id = ?", (prop["id"],))
        existing = c.fetchone()
        if existing:
            if existing[0] != prop["price"]:
                print(f"💰 価格変更: {prop['title']} → {prop['price']}万円")
                changed_titles.append(prop["title"])
            c.execute("UPDATE properties SET price=?, last_seen=? WHERE id=?",
                      (prop["price"], today, prop["id"]))
        else:
            c.execute("""INSERT INTO properties 
                (id, title, price, size, location, url, last_seen, first_seen, madori, chikunensu, type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (prop["id"], prop["title"], prop["price"], prop["size"],
                       prop["location"], prop["url"], today, today,
                       prop["madori"], prop["chikunensu"], prop["type"]))
    conn.commit()
    return changed_titles

def generate_report():
    df = pd.read_sql_query("SELECT * FROM properties ORDER BY price ASC", conn)
    df["更新日"] = pd.to_datetime(df["last_seen"]).dt.strftime("%Y-%m-%d")
    for col in ["madori", "chikunensu", "type"]:
        if col not in df.columns:
            df[col] = ""
    filename = f"report_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(filename, index=False)
    return filename

def daily_task():
    all_props = []

    all_props += fetch_properties(
        "https://www.e-uchina.net/house/urasoeshi/uchima?priceHigh=5000&priceLow=2000&sizeLow1=80", "house")
    all_props += fetch_properties(
        "https://www.e-uchina.net/mansion/urasoeshi/jitchaku,miyagi,uchima?priceHigh=5000&priceLow=2000&sizeLow1=80", "mansion")

    changed_titles = update_database(all_props)
    report = generate_report()

    msg = f"物件情報を更新しました（{len(all_props)}件）\n"
    msg += f"💰 価格変更: {len(changed_titles)}件\n"
    msg += datetime.now().strftime('%Y/%m/%d')

    send_line_message(msg)
    send_email_notification("【物件情報更新】", msg)
    print("✅ 完了：通知とレポート作成")

if __name__ == "__main__":
    daily_task()
