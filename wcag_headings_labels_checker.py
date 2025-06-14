#!/usr/bin/env python3
# WCAG Headings and Labels Checker (WCAG 2.4.6)
# ==========================================
#
# 使い方 (Usage):
#   python wcag_headings_labels_checker.py [URL]
#
# 説明:
#   このツールはWebページをチェックして、見出しとラベルの説明性（WCAG 2.4.6）を
#   評価します。ページ内のすべての見出し（h1-h6）とフォームラベルを分析し、
#   それらが適切にトピックや目的を説明しているかを検証します。
#
# 出力:
#   - コマンドラインに詳細なレポートを表示
#     - 見出しとラベルの一覧
#     - 各要素の説明性評価
#     - WCAG 2.4.6への準拠状況
#
# 必要条件:
#   - Python 3.7以上
#   - Chrome/Chromiumブラウザ
#   - ChromeDriver
#   - Anthropic API キー（config.pyに設定）
#   - 依存パッケージ（requirements.txtに記載）

import sys
import time
import json
import os
import tempfile
import shutil
import anthropic
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import ANTHROPIC_API_KEY, CHROME_BINARY_PATH, CHROME_DRIVER_PATH, DEBUG

def normalize_text(text):
    """
    Normalize text for comparison:
    - Convert full-width characters to half-width
    - Replace special characters with spaces
    - Normalize whitespace
    """
    if not text:
        return ''
    
    # 全角スペースを半角に変換
    text = text.replace('　', ' ')
    
    # 記号の正規化（日本語文字は保持）
    conversion = {
        '！': '!', '？': '?', '：': ':', '；': ';',
        '（': '(', '）': ')', '［': '[', '］': ']',
        '｛': '{', '｝': '}', '．': '.', '，': ',',
        '‼': '!!', '⁉': '!?', '⁈': '?!',
        '〜': '~', '～': '~', '―': '-',
        '…': '...'
    }
    text = text.translate(str.maketrans(conversion))
    
    # 制御文字を半角スペースに変換（日本語文字は保持）
    text = ''.join(c if c.isprintable() or c.isspace() else ' ' for c in text)
    
    # 連続する空白を単一の半角スペースに変換し、前後の空白を削除
    return ' '.join(text.split())

def setup_driver():
    """
    Set up and return a Chrome WebDriver instance
    """
    options = Options()
    options.binary_location = CHROME_BINARY_PATH
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-infobars')
    options.add_argument('--headless=new')
    options.add_argument('--disable-setuid-sandbox')
    
    # Add these arguments to help with the DevToolsActivePort issue
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-background-networking')
    options.add_argument('--disable-prompt-on-repost')
    options.add_argument('--disable-sync')
    
    # Use a dedicated temporary directory for Chrome data
    temp_dir = tempfile.mkdtemp()
    options.add_argument(f'--user-data-dir={temp_dir}')
    options.add_argument('--data-path=' + os.path.join(temp_dir, 'data'))
    options.add_argument('--homedir=' + os.path.join(temp_dir, 'home'))
    options.add_argument('--disk-cache-dir=' + os.path.join(temp_dir, 'cache'))

    service = Service(executable_path=CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver, temp_dir

def cleanup_temp_dir(temp_dir):
    """
    Clean up temporary directory after the driver is closed
    """
    try:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"一時ディレクトリを削除しました: {temp_dir}")
    except Exception as e:
        print(f"警告: 一時ディレクトリの削除に失敗しました: {e}")

def get_page_content(driver):
    """
    Get the page content and parse it with BeautifulSoup, and store WebElements
    """
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Store WebElements for later XPath generation
    elements = {}
    
    # Find all headings and labels using Selenium
    for level in range(1, 7):
        heading_elements = driver.find_elements(By.TAG_NAME, f'h{level}')
        for element in heading_elements:
            try:
                xpath = driver.execute_script("""
                    function getXPath(element) {
                        if (element.id !== '')
                            return `//*[@id="${element.id}"]`;
                        if (element === document.body)
                            return '/html/body';
                        let path = '';
                        while (element.parentNode) {
                            const parent = element.parentNode;
                            const siblings = Array.from(parent.children).filter(e => e.tagName === element.tagName);
                            const index = siblings.indexOf(element) + 1;
                            path = `/${element.tagName.toLowerCase()}${siblings.length > 1 ? `[${index}]` : ''}${path}`;
                            element = parent;
                            if (element === document.body) break;
                        }
                        return `/html/body${path}`;
                    }
                    return getXPath(arguments[0]);
                """, element)
                # 要素の一意の識別子を生成
                tag_name = element.get_attribute("tagName").lower()
                element_id = element.get_attribute("id")
                # 複数の方法でテキストを取得（非表示要素のテキストも取得）
                visible_text = normalize_text(element.text or '')
                inner_text = normalize_text(element.get_attribute("innerText") or '')
                text_content = normalize_text(element.get_attribute("textContent") or '')
                
                # 最も長いテキストを使用
                text = max([visible_text, inner_text, text_content], key=len)
                
                # テキストが空の場合、alt属性やaria-label属性の値を取得
                if not text:
                    alt_text = element.get_attribute("alt")
                    aria_label = element.get_attribute("aria-label")
                    aria_labelledby = element.get_attribute("aria-labelledby")
                    
                    if alt_text:
                        text = normalize_text(alt_text)
                    elif aria_label:
                        text = normalize_text(aria_label)
                    elif aria_labelledby:
                        # aria-labelledbyで参照される要素のテキストを取得
                        try:
                            labelledby_element = driver.find_element(By.ID, aria_labelledby)
                            text = normalize_text(labelledby_element.text or '')
                        except:
                            pass
                    
                    # 要素内のimg要素のalt属性を確認
                    if not text:
                        try:
                            img_elements = element.find_elements(By.TAG_NAME, 'img')
                            for img in img_elements:
                                img_alt = img.get_attribute("alt")
                                if img_alt:
                                    text = normalize_text(img_alt)
                                    break
                        except:
                            pass
                
                # XPATHを識別子として使用
                elements[xpath] = {
                    'tag': tag_name,
                    'id': element_id,
                    'text': text,
                    'xpath': xpath,
                    'alt': element.get_attribute("alt") or '',
                    'aria_label': element.get_attribute("aria-label") or '',
                    'aria_labelledby': element.get_attribute("aria-labelledby") or ''
                }
                
                if DEBUG:
                    print(f"Generated XPath: {xpath}")
                    print(f"Element text: {text}")
            except Exception as e:
                if DEBUG:
                    print(f"Warning: XPath generation failed for element {element.tag_name}: {e}")
                pass
    
    label_elements = driver.find_elements(By.TAG_NAME, 'label')
    for element in label_elements:
        try:
            xpath = driver.execute_script("""
                function getXPath(element) {
                    if (element.id !== '')
                        return `//*[@id="${element.id}"]`;
                    if (element === document.body)
                        return '/html/body';
                    let path = '';
                    while (element.parentNode) {
                        const parent = element.parentNode;
                        const siblings = Array.from(parent.children).filter(e => e.tagName === element.tagName);
                        const index = siblings.indexOf(element) + 1;
                        path = `/${element.tagName.toLowerCase()}${siblings.length > 1 ? `[${index}]` : ''}${path}`;
                        element = parent;
                        if (element === document.body) break;
                    }
                    return `/html/body${path}`;
                }
                return getXPath(arguments[0]);
            """, element)
            # 要素の一意の識別子を生成
            tag_name = element.get_attribute("tagName").lower()
            element_id = element.get_attribute("id")
            # 複数の方法でテキストを取得（非表示要素のテキストも取得）
            visible_text = normalize_text(element.text or '')
            inner_text = normalize_text(element.get_attribute("innerText") or '')
            text_content = normalize_text(element.get_attribute("textContent") or '')
            
            # 最も長いテキストを使用
            text = max([visible_text, inner_text, text_content], key=len)
            
            # テキストが空の場合、alt属性やaria-label属性の値を取得
            if not text:
                alt_text = element.get_attribute("alt")
                aria_label = element.get_attribute("aria-label")
                aria_labelledby = element.get_attribute("aria-labelledby")
                for_attr = element.get_attribute("for")
                
                if alt_text:
                    text = normalize_text(alt_text)
                elif aria_label:
                    text = normalize_text(aria_label)
                elif aria_labelledby:
                    # aria-labelledbyで参照される要素のテキストを取得
                    try:
                        labelledby_element = driver.find_element(By.ID, aria_labelledby)
                        text = normalize_text(labelledby_element.text or '')
                    except:
                        pass
                elif for_attr:
                    # forで参照される要素のplaceholder属性を取得
                    try:
                        for_element = driver.find_element(By.ID, for_attr)
                        placeholder = for_element.get_attribute("placeholder")
                        if placeholder:
                            text = normalize_text(placeholder)
                    except:
                        pass
                
                # 要素内のimg要素のalt属性を確認
                if not text:
                    try:
                        img_elements = element.find_elements(By.TAG_NAME, 'img')
                        for img in img_elements:
                            img_alt = img.get_attribute("alt")
                            if img_alt:
                                text = normalize_text(img_alt)
                                break
                    except:
                        pass
            
            # XPATHを識別子として使用
            elements[xpath] = {
                'tag': tag_name,
                'id': element_id,
                'text': text,
                'xpath': xpath,
                'alt': element.get_attribute("alt") or '',
                'aria_label': element.get_attribute("aria-label") or '',
                'aria_labelledby': element.get_attribute("aria-labelledby") or '',
                'for': element.get_attribute("for") or ''
            }
            
            if DEBUG:
                print(f"Generated XPath: {xpath}")
                print(f"Element text: {text}")
        except Exception as e:
            if DEBUG:
                print(f"Warning: XPath generation failed for element {element.tag_name}: {e}")
            pass
    
    return soup, elements

def extract_headings(soup, elements):
    """
    Extract all headings (h1-h6) from the page
    """
    headings = []
    for level in range(1, 7):
        for heading in soup.find_all(f'h{level}'):
            text = heading.get_text(strip=True)
            headings.append({
                'type': f'h{level}',
                'text': text,
                'html': str(heading),
                'context': get_element_context(heading),
                'element_xpath': next(
                    (info['xpath'] for xpath, info in elements.items()
                     if info['tag'] == f'h{level}' and
                     normalize_text(info['text']).replace(' ', '') == normalize_text(text).replace(' ', '')),
                    next(
                        (info['xpath'] for xpath, info in elements.items()
                         if info['tag'] == f'h{level}' and
                         normalize_text(info['text']) in normalize_text(text) or normalize_text(text) in normalize_text(info['text'])),
                        next(
                            (info['xpath'] for xpath, info in elements.items()
                             if info['tag'] == f'h{level}'),
                            'Unknown'
                        )
                    )
                )
            })
            
            # デバッグ出力
            if DEBUG:
                normalized_text = normalize_text(text)
                matches = [(xpath, info) for xpath, info in elements.items()
                          if info['tag'] == f'h{level}' and
                          normalize_text(info['text']) == normalized_text]
                if not matches:
                    print(f"Warning: No matching XPath found for heading: {text}")
                    print(f"Available {f'h{level}'} elements:")
                    for xpath, info in elements.items():
                        if info['tag'] == f'h{level}':
                            print(f"  Text: '{info['text']}'")
                            print(f"  XPath: {xpath}")
    return headings

def extract_labels(soup, elements):
    """
    Extract all form labels from the page
    """
    labels = []
    for label in soup.find_all('label'):
        # Get the associated form control
        control_id = label.get('for')
        control = soup.find(id=control_id) if control_id else None
        
        text = label.get_text(strip=True)
        labels.append({
            'type': 'label',
            'text': text,
            'html': str(label),
            'control_type': control.name if control else None,
            'control_id': control_id,
            'context': get_element_context(label),
            'element_xpath': next(
                (info['xpath'] for xpath, info in elements.items()
                 if info['tag'] == 'label' and
                 normalize_text(info['text']).replace(' ', '') == normalize_text(text).replace(' ', '')),
                next(
                    (info['xpath'] for xpath, info in elements.items()
                     if info['tag'] == 'label' and
                     normalize_text(info['text']) in normalize_text(text) or normalize_text(text) in normalize_text(info['text'])),
                    next(
                        (info['xpath'] for xpath, info in elements.items()
                         if info['tag'] == 'label'),
                        'Unknown'
                    )
                )
            )
        })
        
        # デバッグ出力
        if DEBUG:
            normalized_text = normalize_text(text)
            matches = [(xpath, info) for xpath, info in elements.items()
                      if info['tag'] == 'label' and
                      normalize_text(info['text']) == normalized_text]
            if not matches:
                print(f"Warning: No matching XPath found for label: {text}")
                print(f"Available label elements:")
                for xpath, info in elements.items():
                    if info['tag'] == 'label':
                        print(f"  Text: '{info['text']}'")
                        print(f"  XPath: {xpath}")
    return labels

def get_element_context(element):
    """
    Get the surrounding context of an element
    """
    # Get parent element
    parent = element.parent
    
    # Get text content before and after the element
    context = {
        'parent_tag': parent.name if parent else None,
        'parent_class': parent.get('class', []) if parent else None,
        'previous_text': element.find_previous_sibling(string=True, strip=True) if element.previous_sibling else None,
        'next_text': element.find_next_sibling(string=True, strip=True) if element.next_sibling else None
    }
    return context


def analyze_elements(elements, url):
    """
    Use Claude to analyze the descriptiveness of headings and labels
    一度に1つの要素を分析し、クライアント側でXPATHを管理する
    """
    client = anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
    )
    
    analyzed_elements = []
    total_elements = len(elements)
    
    print(f"合計 {total_elements} 個の要素を分析します...")
    
    # 各要素を個別に分析
    for index, element in enumerate(elements):
        element_type = element['type']
        element_text = element['text']
        element_xpath = element.get('element_xpath', 'Unknown')
        
        print(f"要素 {index+1}/{total_elements} を分析中: {element_type} '{element_text}'")
        
        # 要素データを準備
        element_data = {
            'type': element_type,
            'text': element_text,
            'html': element['html'],
            'context': element['context']
        }
        
        if 'control_type' in element:
            element_data['control_type'] = element['control_type']
            element_data['control_id'] = element['control_id']
        
        # 要素データをJSON形式に変換
        element_json = json.dumps(element_data, ensure_ascii=False, indent=2)
        
        # Claudeへのプロンプトを作成
        prompt = f"""# あなたはWCAG 2.4.6 見出しとラベルの評価を専門とするアクセシビリティテストの専門家です。
あなたの任務は、見出しとラベルが適切にトピックや目的を説明しているかを分析することです。

# WCAG 2.4.6 見出しとラベルの要件:
見出しとラベルは、トピックや目的を説明していること。

# 評価基準:
1. 見出し（h1-h6）について：
   - ページの構造を適切に表現しているか
   - セクションの内容を明確に説明しているか
   - 階層構造が論理的か
   - 一意で具体的な説明になっているか

2. ラベルについて：
   - フォーム要素の目的を明確に説明しているか
   - ユーザーに求める入力内容が明確か
   - 一意で具体的な説明になっているか

# テスト対象のページ: {url}

# 以下の要素を分析してください：
1. 説明性が十分か（true/false）
2. 現在の説明の評価
3. 改善が必要な場合は具体的な推奨事項

# 回答のフォーマット:
{{
  "descriptive": true/false,
  "evaluation": "評価コメント",
  "recommendations": [
    "推奨事項1",
    "推奨事項2"
  ]
}}

# 分析対象の要素:
{element_json}"""

        try:
            # Claudeに分析リクエストを送信
            message = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1000,
                system="あなたはWCAGコンプライアンス評価、特に見出しとラベルの説明性に特化したアクセシビリティテストの専門家です。",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = str(message.content[0].text)
            
            if DEBUG:
                print("\n=== Claudeの分析結果 ===")
                print(response_text)
            
            # JSONを抽出して解析
            import json5
            
            # JSONを抽出
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                
                try:
                    # JSON5でパース
                    result = json5.loads(json_str)
                    
                    # 分析結果に元の要素情報を追加
                    result['type'] = element_type
                    result['text'] = element_text
                    result['element_xpath'] = element_xpath
                    
                    # 推奨事項がない場合は空リストを設定
                    if 'recommendations' not in result:
                        result['recommendations'] = []
                    
                    analyzed_elements.append(result)
                    print(f"要素 {index+1}/{total_elements} の分析が完了しました")
                    
                except Exception as e:
                    print(f"JSON解析エラー: {e}")
                    # エラーが発生した場合でも、基本的な情報を含む要素を追加
                    analyzed_elements.append({
                        'type': element_type,
                        'text': element_text,
                        'element_xpath': element_xpath,
                        'descriptive': False,
                        'evaluation': "分析中にエラーが発生しました",
                        'recommendations': ["再分析を試みてください"]
                    })
            else:
                print("JSONが見つかりませんでした")
                # JSONが見つからない場合でも、基本的な情報を含む要素を追加
                analyzed_elements.append({
                    'type': element_type,
                    'text': element_text,
                    'element_xpath': element_xpath,
                    'descriptive': False,
                    'evaluation': "分析結果からJSONを抽出できませんでした",
                    'recommendations': ["再分析を試みてください"]
                })
                
        except Exception as e:
            print(f"エラー: Claudeへのリクエスト中に問題が発生しました: {e}")
            # エラーが発生した場合でも、基本的な情報を含む要素を追加
            analyzed_elements.append({
                'type': element_type,
                'text': element_text,
                'element_xpath': element_xpath,
                'descriptive': False,
                'evaluation': f"Claudeへのリクエスト中にエラーが発生しました: {e}",
                'recommendations': ["再分析を試みてください"]
            })
    
    print(f"すべての要素（{len(analyzed_elements)}個）の分析が完了しました")
    return analyzed_elements

def check_headings_and_labels(url):
    """
    Check headings and labels on a webpage
    """
    try:
        print("Chrome WebDriverを設定中...")
        driver, temp_dir = setup_driver()
        print(f"Chrome WebDriverの設定が完了しました。一時ディレクトリ: {temp_dir}")
    except Exception as e:
        print(f"Chrome WebDriverの設定エラー: {e}")
        if "DevToolsActivePort file doesn't exist" in str(e):
            print("\nDevToolsActivePortエラーのトラブルシューティング:")
            print("1. Chromeがインストールされており、実行可能であることを確認してください")
            print("2. 実行中のChromeプロセスがないか確認してください")
            print("3. config.pyのChrome実行ファイルパスが正しいか確認してください")
            print(f"4. 現在のChrome実行ファイルパス: {CHROME_BINARY_PATH}")
            print(f"5. 現在のChromeDriverパス: {CHROME_DRIVER_PATH}")
        raise

    try:
        # Navigate to URL
        print(f"URLに移動中: {url}")
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        print("ページの読み込みが完了しました")
        
        # Parse page content and get element XPaths
        soup, elements = get_page_content(driver)
        
        # 直接Seleniumで取得した要素を使用
        all_elements = []
        
        # 見出し要素を直接追加
        heading_count = 0
        for level in range(1, 7):
            for xpath, info in elements.items():
                if info['tag'] == f'h{level}':
                    heading_count += 1
                    # テキスト情報を構築（テキストが空の場合は代替テキストを使用）
                    element_text = info['text']
                    alt_info = ""
                    if not element_text:
                        if 'alt' in info and info['alt']:
                            element_text = info['alt']
                            alt_info = f" [alt属性から]"
                        elif 'aria_label' in info and info['aria_label']:
                            element_text = info['aria_label']
                            alt_info = f" [aria-label属性から]"
                        elif 'aria_labelledby' in info and info['aria_labelledby']:
                            alt_info = f" [aria-labelledby属性: {info['aria_labelledby']}]"
                    
                    # HTML表現を構築
                    html = f"<{info['tag']}"
                    if 'id' in info and info['id']:
                        html += f" id=\"{info['id']}\""
                    if 'alt' in info and info['alt']:
                        html += f" alt=\"{info['alt']}\""
                    if 'aria_label' in info and info['aria_label']:
                        html += f" aria-label=\"{info['aria_label']}\""
                    if 'aria_labelledby' in info and info['aria_labelledby']:
                        html += f" aria-labelledby=\"{info['aria_labelledby']}\""
                    html += f">{element_text}</{info['tag']}>"
                    
                    all_elements.append({
                        'type': f'h{level}',
                        'text': element_text + alt_info,
                        'html': html,
                        'context': {'parent_tag': 'div', 'parent_class': None, 'previous_text': None, 'next_text': None},
                        'element_xpath': xpath
                    })
        
        # ラベル要素を直接追加
        label_count = 0
        for xpath, info in elements.items():
            if info['tag'] == 'label':
                label_count += 1
                # テキスト情報を構築（テキストが空の場合は代替テキストを使用）
                element_text = info['text']
                alt_info = ""
                if not element_text:
                    if 'alt' in info and info['alt']:
                        element_text = info['alt']
                        alt_info = f" [alt属性から]"
                    elif 'aria_label' in info and info['aria_label']:
                        element_text = info['aria_label']
                        alt_info = f" [aria-label属性から]"
                    elif 'aria_labelledby' in info and info['aria_labelledby']:
                        alt_info = f" [aria-labelledby属性: {info['aria_labelledby']}]"
                    elif 'for' in info and info['for']:
                        alt_info = f" [for属性: {info['for']}]"
                
                # HTML表現を構築
                html = f"<{info['tag']}"
                if 'id' in info and info['id']:
                    html += f" id=\"{info['id']}\""
                if 'for' in info and info['for']:
                    html += f" for=\"{info['for']}\""
                if 'alt' in info and info['alt']:
                    html += f" alt=\"{info['alt']}\""
                if 'aria_label' in info and info['aria_label']:
                    html += f" aria-label=\"{info['aria_label']}\""
                if 'aria_labelledby' in info and info['aria_labelledby']:
                    html += f" aria-labelledby=\"{info['aria_labelledby']}\""
                html += f">{element_text}</{info['tag']}>"
                
                all_elements.append({
                    'type': 'label',
                    'text': element_text + alt_info,
                    'html': html,
                    'context': {'parent_tag': 'form', 'parent_class': None, 'previous_text': None, 'next_text': None},
                    'control_type': None,
                    'control_id': info['id'],
                    'element_xpath': xpath
                })
        
        print(f"見出し要素を {heading_count} 個見つけました")
        print(f"ラベル要素を {label_count} 個見つけました")
        analyzed_elements = analyze_elements(all_elements, url)
        
        if analyzed_elements:
            # Create final report
            descriptive_elements = [e for e in analyzed_elements if e['descriptive']]
            non_descriptive_elements = [e for e in analyzed_elements if not e['descriptive']]
            
            final_report = {
                "url": url,
                "total_elements": len(all_elements),
                "total_headings": heading_count,
                "total_labels": label_count,
                "descriptive_elements": len(descriptive_elements),
                "non_descriptive_elements": len(non_descriptive_elements),
                "descriptive_elements_details": descriptive_elements,
                "non_descriptive_elements_details": non_descriptive_elements,
                "wcag_2_4_6_compliant": len(non_descriptive_elements) == 0
            }
            
            return final_report
            
    finally:
        driver.quit()
        cleanup_temp_dir(temp_dir)

def print_report(report):
    """
    Print the analysis report in a readable format
    """
    print("\n=== WCAG 2.4.6 準拠性レポート ===")
    print(f"URL: {report['url']}")
    print(f"\n総要素数: {report['total_elements']}")
    print(f"見出し数: {report['total_headings']}")
    print(f"ラベル数: {report['total_labels']}")
    print(f"\n説明的な要素: {report['descriptive_elements']}")
    print(f"改善が必要な要素: {report['non_descriptive_elements']}")
    print(f"\nWCAG 2.4.6 準拠状況: {'準拠' if report['wcag_2_4_6_compliant'] else '非準拠'}")
    
    # すべての要素の詳細を出力
    print("\n=== すべての要素の詳細 ===")
    
    # 説明的な要素（問題ない要素）の詳細
    if report['descriptive_elements_details']:
        for element in report['descriptive_elements_details']:
            print(f"\n要素タイプ: {element['type']}")
            print(f"改善の要否: 問題なし")
            print(f"テキスト: {element['text']}")
            print(f"XPATH: {element.get('element_xpath', '不明')}")
            print(f"評価: {element['evaluation']}")
    
    # 改善が必要な要素の詳細
    if report['non_descriptive_elements_details']:
        for element in report['non_descriptive_elements_details']:
            print(f"\n要素タイプ: {element['type']}")
            print(f"改善の要否: 改善が必要")
            print(f"テキスト: {element['text']}")
            print(f"XPATH: {element.get('element_xpath', '不明')}")
            print(f"評価: {element['evaluation']}")
            if element['recommendations']:
                print("改善推奨:")
                for rec in element['recommendations']:
                    print(f"- {rec}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python wcag_headings_labels_checker.py url")
        sys.exit(1)
    
    url = sys.argv[1]
    try:
        report = check_headings_and_labels(url)
        if report:
            print_report(report)
        else:
            print("エラー: レポートの生成に失敗しました")
            sys.exit(1)
    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()