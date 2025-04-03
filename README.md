# WCAG Headings and Labels Checker

## Overview
WCAG Headings and Labels Checker is a tool that evaluates web pages for compliance with WCAG 2.4.6 (Headings and Labels) accessibility requirements. This tool analyzes headings and form labels on a webpage and uses AI-powered analysis to determine whether they adequately describe their topic or purpose.

## Installation
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/wcag_headings_labels_checker
   cd wcag_headings_labels_checker
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install Chrome/Chromium browser if not already installed.

4. Download the appropriate ChromeDriver for your Chrome version from [ChromeDriver website](https://chromedriver.chromium.org/downloads).

5. Create a `config.py` file with the following content:
   ```python
   ANTHROPIC_API_KEY = "your_anthropic_api_key"
   CHROME_BINARY_PATH = "/path/to/chrome"  # e.g., "/usr/bin/google-chrome"
   CHROME_DRIVER_PATH = "/path/to/chromedriver"  # e.g., "/usr/local/bin/chromedriver"
   DEBUG = False  # Set to True for verbose output
   ```

## Usage
Run the tool by providing a URL to check:
```
python wcag_headings_labels_checker.py https://example.com
```

The tool will:
1. Open the webpage in a headless Chrome browser
2. Extract all headings (h1-h6) and form labels
3. Analyze each element's context and content
4. Evaluate whether each heading and label adequately describes its topic or purpose
5. Generate a detailed report showing:
   - Total number of headings and labels
   - Elements that adequately describe their topic/purpose
   - Elements that need improvement
   - Overall WCAG 2.4.6 compliance status

## Notes
- The tool requires an Anthropic API key to use Claude for content analysis.
- The analysis process may take several minutes depending on the number of elements on the page.
- For accurate results, ensure the ChromeDriver version matches your Chrome browser version.

## License
This project is licensed under the MIT License - see the LICENSE file for details.

---

# WCAG 見出しとラベルチェッカー

## 概要
WCAG 見出しとラベルチェッカーは、ウェブページがWCAG 2.4.6（見出しとラベル）アクセシビリティ要件に準拠しているかを評価するツールです。このツールは、ウェブページ上の見出しとフォームラベルを分析し、AI支援の分析を使用して、それらが適切にトピックや目的を説明しているかどうかを判断します。

## インストール方法
1. リポジトリをクローンします：
   ```
   git clone https://github.com/yourusername/wcag_headings_labels_checker
   cd wcag_headings_labels_checker
   ```

2. 必要な依存関係をインストールします：
   ```
   pip install -r requirements.txt
   ```

3. Chrome/Chromiumブラウザがインストールされていない場合はインストールします。

4. お使いのChromeバージョンに適合するChromeDriverを[ChromeDriverウェブサイト](https://chromedriver.chromium.org/downloads)からダウンロードします。

5. 以下の内容で`config.py`ファイルを作成します：
   ```python
   ANTHROPIC_API_KEY = "あなたのAnthropic APIキー"
   CHROME_BINARY_PATH = "/Chromeへのパス"  # 例："/usr/bin/google-chrome"
   CHROME_DRIVER_PATH = "/ChromeDriverへのパス"  # 例："/usr/local/bin/chromedriver"
   DEBUG = False  # 詳細な出力が必要な場合はTrueに設定
   ```

## 使い方
チェックするURLを指定してツールを実行します：
```
python wcag_headings_labels_checker.py https://example.com
```

このツールは以下を行います：
1. ヘッドレスChromeブラウザでウェブページを開く
2. すべての見出し（h1-h6）とフォームラベルを抽出
3. 各要素のコンテキストと内容を分析
4. 各見出しとラベルが適切にトピックや目的を説明しているかを評価
5. 詳細なレポートを生成：
   - 見出しとラベルの総数
   - トピック/目的を適切に説明している要素
   - 改善が必要な要素
   - WCAG 2.4.6への全体的な準拠状況

## 注意点
- このツールは内容分析にClaudeを使用するため、Anthropic APIキーが必要です。
- 分析プロセスは、ページ上の要素の数によって数分かかる場合があります。
- 正確な結果を得るために、ChromeDriverのバージョンがお使いのChromeブラウザのバージョンと一致していることを確認してください。

## ライセンス
このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。