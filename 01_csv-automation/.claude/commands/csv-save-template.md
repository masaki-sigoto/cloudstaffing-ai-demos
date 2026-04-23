---
description: ヘッダーマッピングを派遣元テンプレートとして保存
---

引数は `<入力CSV> <テンプレート名>` の順で与えられます（例: `samples/timesheet_202604_haken_a.csv haken_a`）。
`python3 src/main.py save-template --input <入力CSV> --name <テンプレート名>` を実行し、保存されたテンプレートJSONの中身（確定したマッピング・信頼度）を簡潔に要約してください。
