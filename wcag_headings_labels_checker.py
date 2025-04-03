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
                text = normalize_text(element.text or '')
                
                # XPATHを識別子として使用
                elements[xpath] = {
                    'tag': tag_name,
                    'id': element_id,
                    'text': text,
                    'xpath': xpath
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
            text = normalize_text(element.text or '')
            
            # XPATHを識別子として使用
            elements[xpath] = {
                'tag': tag_name,
                'id': element_id,
                'text': text,
                'xpath': xpath
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
                     normalize_text(info['text']) == normalize_text(text)),
                    'Unknown'
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
                 normalize_text(info['text']) == normalize_text(text)),
                'Unknown'
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
    """
    client = anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
    )
    
    # Prepare elements data for analysis
    elements_data = []
    for element in elements:
        element_data = {
            'type': element['type'],
            'text': element['text'],
            'html': element['html'],
            'context': element['context'],
            'element_xpath': element.get('element_xpath', 'Unknown')
        }
        if 'control_type' in element:
            element_data['control_type'] = element['control_type']
            element_data['control_id'] = element['control_id']
        elements_data.append(element_data)
    
    # Format the elements data as JSON
    elements_json = json.dumps({"elements": elements_data}, ensure_ascii=False, indent=2)
    
    # Create the prompt for Claude
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

# 以下の要素を分析してください。各要素について：
1. 説明性が十分か（true/false）
2. 現在の説明の評価
3. 改善が必要な場合は具体的な推奨事項

# 回答のフォーマット:
{{
  "elements": [
    {{
      "type": "h1",
      "text": "ページタイトル",
      "descriptive": true,
      "evaluation": "明確で具体的なタイトルです",
      "recommendations": []
    }},
    {{
      "type": "label",
      "text": "姓",
      "descriptive": false,
      "evaluation": "ラベルが簡素すぎます",
      "recommendations": [
        "「姓（例：山田）」のように例を追加する",
        "必須項目の場合はその旨を明記する"
      ]
    }}
  ]
}}

# 分析対象の要素:
{elements_json}"""

    print("Claudeに見出しとラベルの分析リクエストを送信中...")
    
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4096,
            system="あなたはWCAGコンプライアンス評価、特に見出しとラベルの説明性に特化したアクセシビリティテストの専門家です。",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = str(message.content[0].text)
        print("\n=== Claudeの分析結果 ===")
        if DEBUG:
            print(response_text)
    except Exception as e:
        print(f"\nエラー: Claudeへのリクエスト中に問題が発生しました: {e}")
        return None

    try:
        # Extract and parse JSON from response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx != -1:
            json_str = response_text[start_idx:end_idx]
            result = json.loads(json_str)
            if 'elements' in result:
                print(f"{len(result['elements'])}個の要素の分析が完了しました")
                return result['elements']
            else:
                print("警告: 応答にelementsフィールドがありません")
    except Exception as e:
        print(f"エラー: Claudeの応答の処理中に問題が発生しました: {e}")
    
    return None

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
        
        # Extract headings and labels
        headings = extract_headings(soup, elements)
        labels = extract_labels(soup, elements)
        
        print(f"見出し要素を {len(headings)} 個見つけました")
        print(f"ラベル要素を {len(labels)} 個見つけました")
        
        # Analyze all elements
        all_elements = headings + labels
        analyzed_elements = analyze_elements(all_elements, url)
        
        if analyzed_elements:
            # Create final report
            descriptive_elements = [e for e in analyzed_elements if e['descriptive']]
            non_descriptive_elements = [e for e in analyzed_elements if not e['descriptive']]
            
            final_report = {
                "url": url,
                "total_elements": len(all_elements),
                "total_headings": len(headings),
                "total_labels": len(labels),
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
    
    if report['non_descriptive_elements_details']:
        print("\n=== 改善が必要な要素 ===")
        for element in report['non_descriptive_elements_details']:
            print(f"\n要素タイプ: {element['type']}")
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