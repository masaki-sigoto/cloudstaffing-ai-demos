# 技術仕様書 レビュー対応履歴

本ファイルは `docs/03_spec.md`（技術仕様書）に対する Codex レビュー指摘と反映履歴を記録する。

---

## Round 1（2026-04-23）

### 入力
- レビューソース: `/tmp/codex_spec_03_r1_clean.txt`
- レビュー対象: `docs/03_spec.md`
- 総合評価: **C**（設計書の重要論点はかなり反映できているが、M-4 実装仕様欠落と PII/出力先制約の具体化不足が Phase5 で手戻りを生む懸念あり）

### Critical 指摘への対応

| # | 指摘（要旨） | 対象§ | 対応 | 反映箇所 |
|---|---|---|---|---|
| C-1 | M-4 チェックリスト出力のI/F欠落。`DispatchCoordinatorReport` / `ClientSiteReport` に `write(..., output_path, response_deadline)` を追加し、`output/checklist/by_coordinator_{YYYYMM}.txt` / `by_client_site_{YYYYMM}.txt` の生成を明記 | §5.10 | 対応済 | §3 ディレクトリ（checklist ファイル名明記）、§5.10（両Report に `write()` 追加） |
| C-2 | PII マスキング適用範囲の不整合。JSON `staff_name` / `assignee_name` が平文残存しうる。全出力共通前処理に固定、JSON も同一ポリシー（IDは非マスク） | §9.3 | 対応済 | §5.8（`PiiMaskingFilter` を全出力の前処理として適用）、§9.3（JSON も名前はマスク、IDのみ非マスクと明文化） |
| C-3 | 出力先制限（realpath/symlink 防止）の実装仕様欠落。`safe_join_output(base, rel)` を共通関数化、`realpath` で `output/` 外なら FATAL(exit=1) | 新規 §5.12 / §8 | 対応済 | §5.12 `safe_join_output` 追加、§8 例外 `OutputPathViolationError` 追加 |
| C-4 | 型/I/F 矛盾。`RULES: list[type[AnomalyRule]]` にインスタンスを代入、`Finding.day_key` 必須性が型で未保証 | §5.6, §4.2 | 対応済 | §5.6 `RULES: list[AnomalyRule]` にインスタンス統一、§4.2 `Finding.__post_init__` で scope ごとの必須項目を強制 |

### Major 指摘への対応

| # | 指摘（要旨） | 対象§ | 対応 | 反映箇所 |
|---|---|---|---|---|
| M-1 | 依存/バージョン固定不十分。`Python 3.10以上` は再現性弱、`pytest` 使うなら固定記載、または `unittest` に統一 | §1.4, §2.1, §10.4 | 対応済（unittest 一本化） | §2.1 Python 3.10.x 明記、§10.4 標準ライブラリ `unittest` に統一（外部依存ゼロ維持） |
| M-2 | エッジケース試験不足。24:00境界、0件入力、CP932/UTF-8混在 | §10 | 対応済 | §10.1 に `test_edge_cases.py` 追加、§10.2 に代表ケース追加、§4.1.1 に「24:00 表記は WARN+skip」追記 |
| M-3 | `response_deadline` の伝播。全出力クラスシグネチャに `response_deadline: date` を含めるべき | §5.10 | 対応済 | §5.10 `JsonResultWriter.write()` / `DispatchCoordinatorReport.write()` / `ClientSiteReport.write()` に `response_deadline` 追加 |
| M-4 | JSON `filters` の仕様差分（`null` vs 空オブジェクト） | §4.3 | 対応済（空オブジェクト寄せ） | §4.3 例の `filters` を `{}` 起点に変更、未指定時は `{}`、指定時のみキーを追加するポリシーを明記 |

### Minor 指摘への対応

| # | 指摘（要旨） | 対応 | 備考 |
|---|---|---|---|
| m-1 | `raw_context: dict` → `Mapping[str, Any]` へ明確化 | 対応済 | §4.2 dataclass 定義を `Mapping[str, object]` に変更 |
| m-2 | 補助モジュール（`models.py`, `errors.py`, `rules/base.py`）を設計書トレーサに補記 | 対応済 | §1.1 対応表に「補助モジュール」脚注追加 |
| m-3 | グループ出力（担当者順／事業所順）のキーソート規約明文化 | 対応済 | 付録B にグループキーのソート規約（`assignee_id` 昇順、`(client_id, client_site)` 昇順）を追記 |

### 見送り

| # | 指摘 | 見送り理由 |
|---|---|---|
| - | （なし） | Round1 は Critical/Major/Minor 全件を反映。見送りはなし。 |

### 結果サマリ
- **Critical**: 4件すべて対応
- **Major**: 4件すべて対応
- **Minor**: 3件すべて対応
- 依存方針は `unittest` に一本化し「標準ライブラリのみ」方針を厳守
- 次ラウンドは反映内容の整合性と安全系ガード（safe_join_output、PII 全層適用）のトレース確認が焦点

---

## ラウンド2 (2026-04-23)

### 入力
- レビューソース: `/tmp/codex_spec_03_r2_clean.txt`
- レビュー対象: `docs/03_spec.md`
- 総合評価: **B**（R1 で重い論点はかなり潰れているが、実装直前としては「仕様同士が同時に満たせない」矛盾が 2 点残存。Phase5 着手前に解消が必須）

### Critical 指摘への対応

| # | 指摘（要旨） | 対象§ | 対応 | 反映箇所 |
|---|---|---|---|---|
| C-1 | 再現性要件が自己矛盾。`processed_at` を毎回記録する仕様なのに、テストで「2回実行してバイト一致」を要求しており成立しない | §10.2 T-AsOfDate-Reproducibility, §9.1 | 対応済 | §9.1 に「`processed_at` を除外した部分木で比較。完全バイト一致は Clock 注入で担保」を追記／§10.2 T-AsOfDate-Reproducibility の期待を「`meta.processed_at` を除外して `json.dumps(sort_keys=True)` で一致」に修正 |
| C-2 | `MatchedCase(staff_id×date)` と `Finding` 必須項目が不整合。DAY/APPLICATION 検知で `client_id/client_site/assignee_id` を一意に決めるルールが未定義 | §4.2 `MatchedCase`, §5.4 `ClientApprovalMatcher` | 対応済 | §4.2 `MatchedCase` のキーを `(staff_id, date, client_id, client_site, assignee_id)` に分割し `day_key` も 5 キー連結に変更／§5.4 `ClientApprovalMatcher` の契約を更新（5 キー合流、混在は別 case 分割、申請のみ行は仮想 case、解決不能は `WARN+skip`） |

### Major 指摘への対応

| # | 指摘（要旨） | 対象§ | 対応 | 反映箇所 |
|---|---|---|---|---|
| M-1 | パス仕様の内部矛盾（§1.4 `src/rules/` vs §3 `src/detection/rules/`） | §1.4 | 対応済 | §1.4 を `src/detection/rules/` に修正し §3 と一致させた |
| M-2 | テスト成果物一覧の不一致（§3 は 4 ファイル+fixtures、§10.1 は 10 ファイル） | §3 | 対応済 | §3 の tests ディレクトリに §10.1 #5〜#10 の 6 ファイルを追記（10 ファイル構成に揃え） |
| M-3 | 設計書との I/F 語彙ズレ（`detect` vs `check`） | §5.5 | 対応済 | §5.5 に「実装仕様としては本節の `check(case, ctx) -> Iterator[Finding]` を唯一の正とする」と明記。設計書 §7.1 の `detect` 表記は概念説明扱いと注記 |
| M-4 | `JsonResultWriter.write` で `response_deadline` の真実源が二重化（`meta` 内と別引数） | §5.10 | 対応済 | §5.10 `JsonResultWriter.write` から `response_deadline` 引数を削除し `meta["response_deadline"]` に一本化。呼出契約も追記 |

### Minor 指摘への対応

| # | 指摘（要旨） | 対応 | 反映箇所 |
|---|---|---|---|
| m-1 | `PiiMaskingFilter` 説明の「additional_patterns 伝播先にも適用」が誤読を招く（`additional_patterns` は ID 配列でマスク対象ではない） | 対応済 | §5.8 `apply` docstring を書き換え、マスク対象は `primary` の `staff_name` / `assignee_name` のみ、`additional_patterns` は pattern_id 配列でマスク対象外、併記時も primary 側の氏名を参照する旨を明記 |
| m-2 | `config` を「純粋計算」と書きつつ `output_dir()` でディレクトリ作成副作用がある | 対応済 | §5.2 責務文を修正し「基本は純粋計算だが `output_dir()` のみディレクトリ作成の副作用を含む」と明示 |

### 見送り

| # | 指摘 | 見送り理由 |
|---|---|---|
| - | （なし） | Round2 指摘は Critical/Major/Minor いずれも軽量な文言・I/F 整合修正で完了可能だったため、全件対応した |

### 結果サマリ
- **Critical**: 2 件すべて対応（再現性矛盾と MatchedCase キー矛盾を解消）
- **Major**: 4 件すべて対応（パス／テスト成果物／I/F 語彙／response_deadline 二重化）
- **Minor**: 2 件すべて対応
- 設計思想（3 者ワークフロー、標準ライブラリのみ、`safe_join_output` による出力先ガード、全出力共通 PII マスク）は維持
- 次ラウンドは C-2 で導入した 5 キー合流が A-01〜A-10 疑似コードと付録 B ソート規約に矛盾なく波及しているかのトレース確認、および `JsonResultWriter` 呼出側コード例の更新が焦点

---

## ラウンド3 (2026-04-23) ※最終

### 入力
- レビューソース: `/tmp/codex_spec_03_r3_clean.txt`
- レビュー対象: `docs/03_spec.md`
- 総合評価: **B（条件付きで Phase5 進行可）**。R1（C）→ R2（B）→ R3（B／A-06 のみ解消必須）の推移。実装着手粒度は十分で、関数シグネチャ・データモデル・疑似コード・例外階層・PII/出力先ガードは実装直結レベル。R2 の 5 キー合流が A-06 の重複検知と両立していない点だけが Phase5 着手前の必須修正事項として指摘された

### Critical 指摘への対応

| # | 指摘（要旨） | 対象§ | 対応 | 反映箇所 |
|---|---|---|---|---|
| C-1 | A-06 が多重発火する設計矛盾。`leaves`/`overtimes` を同日全 case に重複配布する設計と `finding_key=day:{day_key}`（client/site/assignee 込み）が両立せず、同一 staff/date で複数 client case があるとき A-06 が case 数ぶん立つ | §4.2, §5.4, §6.6 | 対応済（A-06 専用キー方式） | §4.2 `Finding.finding_key` に A-06 分岐を追加し `a06:{staff_id}:{date}:{branch}` へ固定／§5.4 ClientApprovalMatcher 契約の注釈を更新／§6.6 A-06 疑似コードに仮想 case ガードと集約挙動を明記／§10.2 に回帰テスト `T-A06-DedupeAcrossCases` を追加／付録C D-12 に決定記録 |

### Major 指摘への対応

| # | 指摘（要旨） | 対象§ | 対応 | 反映箇所 |
|---|---|---|---|---|
| M-1 | `_pick_primary` 規約未定義で表示 severity と `score_breakdown` の説明軸が食い違う余地 | §5.7, §6.12 | 対応済 | §5.7 に `_pick_primary` シグネチャと契約を追加／§6.12 に 3 段 tie-break（スコア降順→`pattern_id`→`record_id`/`application_id`→入力順）の実装例を明記／付録C D-13 |
| M-2 | `approver_statuses`（モデル複数値）と JSON `approver_status`（単数）の型不整合 | §4.2, §4.3 | 対応済（複数形配列に統一） | §4.3 JSON 例を `approver_statuses: ["pending"]` に変更、ポリシー節を追加。単一化ルールは設けず、`JsonResultWriter` が `tuple[str, ...]` をそのまま配列化／付録C D-14 |
| M-3 | `safe_join_output` の安全保証が仕様文より弱く、「全て弾く」が過剰表現 | §5.11 | 対応済（文言修正） | §5.11 docstring を「通常のパストラバーサル防止」に書き換え、`resolve(strict=False)` ベースのため TOCTOU／後置 symlink は保証外と明示。将来強化案（`O_NOFOLLOW` 相当）も注記／付録C D-15 |

### Minor 指摘への対応

| # | 指摘（要旨） | 対応 | 反映箇所 |
|---|---|---|---|
| m-1 | `calendar` / `sys` / `collections` が依存一覧未記載 | 対応済 | §2.2 依存表に 3 モジュールを追記（疑似コードでの使用箇所を注記） |
| m-2 | `timesheet.client_site` が「必須」かつ「欠損時 unknown 継続」で契約が揺れる | 対応済 | §4.1.1 の必須欄を「○（論理必須）」に変更し、列は必須・値は補完ありのニュアンスを明文化 |

### 見送り

| # | 指摘 | 見送り理由 |
|---|---|---|
| - | （なし） | R3 は Critical 1 件／Major 3 件／Minor 2 件、すべて軽量な I/F・文言修正で完結。見送りはなし |

### 結果サマリ
- **Critical**: 1 件対応（A-06 重複検知を専用キー方式で解消）
- **Major**: 3 件すべて対応（primary 決定規約明文化／`approver_statuses` 配列統一／`safe_join_output` 文言緩和）
- **Minor**: 2 件すべて対応
- 設計思想（3 者ワークフロー、A-01〜A-10、重要度 3 軸スコア、標準ライブラリのみ、`safe_join_output`、全出力共通 PII マスク）はすべて維持
- 総合評価の推移: R1 **C** → R2 **B** → R3 **B（Phase5 着手可）**

---

## 最終残論点

Round3 時点で Phase5（実装）着手可と判断。ただし以下は「仕様としては確定したが実装時に再確認する観点」として明記しておく（いずれも実装の手が止まるレベルではない）。

1. **A-06 `finding_key` の運用確認**: `a06:{staff_id}:{date}:{branch}` を採用したことで、複数 case にまたがる `leave_vs_punch` / `overtime_missing` が集約される。集約後の `primary` に載る `client_id` / `client_site` / `assignee_id` は入力順で最初に発火した case のものが採られるため、通知／チェックリストの宛先担当者が「必ずしも全 case 網羅ではない」ことをデモ時の口頭説明で補う（仕様上の妥当性は担保、UX の説明コストのみ残る）
2. **`safe_join_output` の保証範囲**: R3 Major 3 で「通常のパストラバーサル防止」にスコープを限定。TOCTOU／後置 symlink 攻撃は仕様外とし、必要時は `O_NOFOLLOW` 相当に引き上げる方針を D-15 に記録済み。本デモでは採用しない
3. **`approver_statuses` の単一化ニーズ**: 表示上 1 件に畳みたい UX 要件が後から出た場合は、JSON 側は配列維持のまま、チェックリスト／通知 txt のレンダラ層で join する方向で対処する（仕様は R3 で `list[str]` 固定）
4. **`_pick_primary` の tie-break 実装テスト**: 3 段 tie-break（スコア→`pattern_id`→`record_id`/`application_id`→入力順）は §6.12 に疑似コード化。`test_severity_scorer.py` に「同スコア複数パターン」ケースを 1 つ足すのが望ましいが、必須ではなく Phase5 実装時に判断
5. **設計書 §7.1 `detect` 表記の残置**: Round2 Major 3 で本仕様書側を「正」と宣言済み。設計書本体の更新は行わない方針のため、実装者は必ず仕様書 §5.5 `check(case, ctx) -> Iterator[Finding]` を参照すること

**Phase5 着手可否**: 可。Critical は全て解消、Major／Minor も全て反映済み。R3 で新規に生じた設計変更（A-06 キー、primary 規約、`approver_statuses` 配列化、`safe_join_output` 保証範囲）は §4〜§6／§10／付録C に全て波及済み。

