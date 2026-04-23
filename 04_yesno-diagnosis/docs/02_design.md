# システム設計書: 運用整備状況 簡易診断アプリ（04_yesno-diagnosis）

> 本書は要件定義書 `01_requirements.md` を受けて、**どう作るか** を中粒度で定義する設計書である。コードレベルの詳細（変数名、CSSクラス名、完全なロジック）は次フェーズの技術仕様書に譲る。

---

## 1. 設計の目的と範囲

### 1.1 このドキュメントの位置付け
- 要件定義書で合意された **運用整備ナビゲーター**（単一HTMLモック）を、実装着手可能な粒度まで分解する。
- 「単一HTMLファイル完結」「外部依存ゼロ」「オフライン動作」という3つの絶対制約を満たす設計指針を固定する。
- 営業／導入支援／顧客担当者の3利用シーンに耐える画面・状態・印刷設計を提示する。

### 1.2 要件定義書との対応関係

| 要件定義書セクション | 本設計書での受け |
|----------------------|------------------|
| §1.5 成果物の形（単一HTML） | §2 アーキテクチャ概要、§3 モジュール配置、付録A ファイル構造 |
| §4 機能要件 M-01〜M-14 | §6 画面体系、§7 判定アルゴリズム、§9 プライバシー |
| §5 非機能要件 | §2、§8、§9、§10 |
| §10 質問フロー（含 §10.3 決定表・§10.3.5 ショート版） | §5 データモデル、§7 アルゴリズム設計 |
| §11 運用パターン | §5 パターン定義、§6 結果カードUI |

### 1.3 次フェーズに委ねる範囲
- CSS 完全版（カラーパレット確定値、余白数値、印刷ピクセル指定）
- 質問文の最終文言レビュー（本設計書ではIDと構造のみ扱う）
- アニメーション詳細（transition の秒数、イージング関数）
- HTML 最終マークアップのアクセシビリティ属性（`aria-*` 細目）

---

## 2. アーキテクチャ概要

### 2.1 全体像（単一HTML内の論理構成）

```
index.html (単一ファイル、目標300KB / 上限1MB)
├── <head>
│   ├── <meta>（charset, viewport, description）
│   └── <style>  ← 全CSSをインライン（画面用 + @media print）
├── <body>
│   ├── #app-header（免責バー：全画面固定、M-14）
│   ├── #app-root（アプリ本体。画面切替はここで行う）
│   │   ├── [screen:splash]    … スプラッシュ／保存モード選択
│   │   ├── [screen:question]  … 質問画面（フル版/ショート版共通レイアウト）
│   │   ├── [screen:result]    … 診断結果カード
│   │   └── [screen:print]     … 印刷プレビュー（2モード：要約/詳細）
│   └── <script>  ← 全JSをインライン（下記5モジュールを1ファイルに集約）
└── （外部CDN・リンク・画像ファイルは一切なし。必要な画像はSVGインライン）
```

### 2.2 論理モジュール（JS内の分割）

同一 `<script>` タグ内で、IIFE ＋ 名前空間で以下5モジュールに論理分割する（物理ファイルは1つ）。

```
AppCore（オーケストレータ：UI/ロジック/描画の接続のみ担当）
├── State      … 状態管理（唯一の真実。セッションメモリ中心）
├── Flow       … 質問フローエンジン（純ロジック：次QID/完了状態を返す）
├── Judge      … 判定エンジン（スコアリング L/A/C/P + 決定表）
├── Render     … 画面レンダラ（screen切替・カード描画・進捗）
└── Persist    … 永続化（localStorage、保存モード時のみ作動）
```

- **AppCore** は Flow/Judge/Render を接続する唯一のオーケストレータ。ユーザー操作（クリック／キー）を起点に、`Flow.next()` の戻り値（次QID or `done`）を見て、`done` なら `Judge.evaluate()` を呼び、結果を `State` へ書き、`Render.show()` を呼ぶ。**Flow から Judge / Render を直接呼ばない**（§3.2 の依存図と一致させるため）。

### 2.3 処理の流れ（ハッピーパス：ショート版）

```
1. ブラウザがindex.htmlを開く
2. Renderがsplash画面表示（保存モードモーダル：初期選択「保存しない」）
3. ユーザが「ショート版で開始」クリック
4. Flow.startShort()：質問列[Q2,Q3,Q5,Q12,Q13,Q6,Q15]をキューに積む
5. Renderがquestion画面表示、Stateに回答記録、Flow.next()で次へ
6. 全問終了→Judge.evaluate(State.answers)→パターン確定
7. Renderがresult画面表示（パターンカード+要ヒアリングタグ）
8. 印刷ボタン→print画面に切替、window.print()呼出し
```

---

## 3. コンポーネント構成

### 3.1 モジュール一覧

| モジュール | 責務 | 依存 | 公開インタフェース（抜粋） |
|-----------|------|------|-----------------------------|
| **AppCore** | オーケストレータ。イベント受信→Flow/Judge 呼出→State更新→Render 呼出の統制のみ | State, Flow, Judge, Render, Persist | `onAnswer(qid, val)`, `onBack()`, `onStart(mode)`, `onRestart()` |
| **State** | 回答・進捗・モード・PII・UI状態を一元保持 | なし（ルート） | `get()`, `setAnswer(qid, val)`, `reset()`, `snapshot()` |
| **Flow** | 質問ツリー走査、分岐判定、ショート版の線形実行、戻る。**DOM非依存ロジック層**（DOM／Judge／Render に触れない。State は読み書きする） | State | `startFull()`, `startShort()`, `next()`（戻り値: `{nextQid}` または `{done:true}`）, `back()`（戻り値: `{prevQid}` または `{noop:true}`）, `current()`, `canGoBack()` |
| **Judge** | L/A/C/Pスコア算出、決定表適用、要ヒアリングタグ生成 | State | `evaluate(answers, mode) → {pattern, scores, tags, subMatches}` |
| **Render** | screen切替、質問描画、結果カード、印刷プレビュー、免責バー | State | `show(screenId)`, `refresh()`, `toPrint(mode)`（Flow/Judge を直接呼ばず、State を読むだけ） |
| **Persist** | localStorage読み書き（保存モード時のみ）、クリア、フォールバック警告 | State | `save()`, `load()`, `clear()`, `isAvailable()`, `hasSavedSession()` 。`load()` は明示同意前は呼ばない（§9.1） |

### 3.2 依存関係図

```
                AppCore（オーケストレータ）
                │   │   │   │   │
        ┌───────┘   │   │   │   └───────┐
        ▼           ▼   ▼   ▼           ▼
      Flow ──► State ◄── Judge        Render ──► State（参照のみ）
                ▲
             Persist
```

- **AppCore** のみが Flow / Judge / Render / Persist を呼び分ける。
- **Flow** は State を読んで次QIDを返すだけ。Judge と Render を呼ばない。
- **Render** は State を読むだけのプレゼンテーション層。Flow/Judge を呼ばない。
- **State** はどこにも依存しない純粋データストア。
- **Persist** は AppCore から明示呼出しモデルで呼ばれる（State 監視は行わない）。

### 3.3 分離の根拠
- 質問追加・パターン追加の**保守性**（要件§5）を確保するため、データ（質問ツリー・パターン定義）とロジック（Flow/Judge）を分離。
- 画面差し替え（スプラッシュ／質問／結果／印刷）のUI制御を Render に集約し、他モジュールをDOM非依存に保つ。
- Persist をオプションモジュール化し、**保存しないモード時は一切呼ばれない**ことを設計レベルで担保（M-11、§9.1）。

---

## 4. データフロー

### 4.1 入力 → 処理 → 出力

```
[入力]
  ユーザのクリック／キー入力（YES/NO/3択）
      │
      ▼
[State.setAnswer(qid, value)]  ← 回答記録
      │
      ▼
[Flow.next()]                   ← 次質問決定（フル版=分岐、ショート版=配列の次）
      │
      ▼  （全問完了時のみ）
[Judge.evaluate()]              ← L/A/C/Pスコア→決定表→パターン確定
      │
      ▼
[State.result = {patternId, priorityMatched, scores, tags, reasonHighlights, subMatches, fallback}]  // §4.2 の result と完全同一スキーマ
      │
      ▼
[Render.show('result')]         ← カードUI描画
      │
      ▼（任意）
[Render.toPrint('summary'|'detail')] → window.print()
```

### 4.2 中間データ形式（要旨）

- **answers**: `{ [qid]: 'YES' | 'NO' | 'UNKNOWN' | 'KYOTEI' | 'KINTOU' | 'PART' | 'NOT_READY' | …}` の辞書（**内部は英字コード値に統一**。日本語は表示ラベル専用で `QUESTIONS[qid].choices[n].label` に分離。比較ロジックは必ずコード値で実装）
- **scores**: `{ L: 1|2|3, A: 1|2|3, C: 1|2|3, P: 'FINE'|'COARSE', flags: {proxyApprovalMissing: true} }`（内部コードは英字統一。表示は §10.2 で日本語化）
- **result**: `{ patternId: 'A'|'B'|'C'|'D'|'E', priorityMatched: 1〜6, subMatches: [...], tags: ['要ヒアリング：Q12不明', ...], reasonHighlights: [{axis:'L', value:3, qids:['Q2']}, ...], fallback: false }`（`reasonHighlights` は結果カードの「該当理由」欄の生成元。Judge が決定表マッチ時に該当軸・値・寄与質問ID配列を格納）

### 4.3 エラー時の分岐フロー

| 異常 | 検知箇所 | 回復 |
|------|---------|------|
| localStorage 利用不可 | Persist.isAvailable() | 画面上部に警告バナー表示、セッションメモリのみで継続（§9.2） |
| 決定表のいずれもマッチせず | Judge.evaluate | フォールバック（優先度6）：最近傍パターン提示＋「要ヒアリング（確定度: 中）」**黄色**バッジ（色は要件§10.2準拠で統一） |
| ショート版で必須質問が未回答 | Flow.next()（戻り値 `{done:true}` 発火直前の AppCore 側ガード） | 次質問を再提示（設計上は発生しないが、戻る操作との兼ね合いで AppCore が未回答検知時に `{nextQid}` を再提示） |
| 印刷APIが呼べない（file://制約等） | Render.toPrint | 印刷プレビュー画面をそのまま表示し、「ブラウザの印刷機能をお使いください」の案内を添える |
| clipboard API 不可 | Render（S-04） | テキスト選択済みモーダル表示（フォールバックUI） |

---

## 5. データモデル / スキーマ

### 5.1 質問定義（JS内定数 `QUESTIONS`）

```
{
  id: 'Q2',
  text: '派遣元として、拠点（営業所・支社）は3箇所以上ありますか？',
  type: 'YN' | 'MULTI',             // 2択は 'YN'、3/4択は 'MULTI'（choices.length で識別）
  choices: [ {value:'YES', label:'はい'}, {value:'NO', label:'いいえ'} ], // 2〜4件
  branch: (state) => nextQid,       // フル版の分岐関数（ショート版では未使用）
  axis: ['L' | 'A' | 'C' | 'P'],    // 関連評価軸
  domain: '組織階層/データ運用',    // 業務領域タグ
  hint: 'S-01向け補足説明文',
  triage: (ans) => {needHearing: bool}, // 要ヒアリング判定
}
```

- Q1〜Q17（Q11は欠番、要件§10.2）を上記形式で配列化。
- `branch` 関数は要件§10.1のツリーをそのまま条件分岐で実装。
- 選択肢数は `choices.length` で判定（2=YN／3=三択／4=四択）。Q16・Q17 の4択もこのスキーマで表現。

### 5.2 パターン定義（JS内定数 `PATTERNS` と `PATTERN_RULES`）

**判定ルールと表示情報は完全分離する**（R2 Critical 2対応）。`PATTERNS` は表示情報のみを持ち、判定条件は `PATTERN_RULES` が単一ソースとして保持する。

#### 5.2.1 `PATTERNS`（表示情報のみ）

```
{
  id: 'C',
  name: '将来拡張対応型',
  summary5: [ '拠点3層構造…', '承認ルート2段階…', … ],  // 要約版印刷で使用
  detail: { org, approval, auth, project, law, extension }, // 詳細カード
  effort: '10〜15営業日',
  cautions: [ '導入プロジェクトとして3ヶ月計画推奨', … ],
}
```

- A〜E の5パターンを要件§11そのまま定義。
- **`condition` / `predicate` は PATTERNS には置かない**（重複源の排除）。

#### 5.2.2 `PATTERN_RULES`（判定単一ソース）

```
PATTERN_RULES = [
  { priority: 1, patternId: 'E',
    ruleLabel: 'C===3（法対応要整備）',
    predicate: (s) => s.C === 3 },
  { priority: 2, patternId: 'C',
    ruleLabel: 'L===3 かつ A>=2 かつ Q15=YES（拠点3層＋拡張計画あり）',
    predicate: (s) => s.L === 3 && s.A >= 2 && s.answers.Q15 === 'YES' },
  { priority: 3, patternId: 'B',
    ruleLabel: '...（B条件の自然文）',
    predicate: (s) => ... },
  { priority: 4, patternId: 'A',
    ruleLabel: '...（A条件の自然文）',
    predicate: (s) => ... },
  { priority: 5, patternId: 'D',
    ruleLabel: '...（D条件の自然文）',
    predicate: (s) => ... },
  // 優先度6（フォールバック）は Judge が nearestPattern で解決。ruleLabel='フォールバック（最近傍, 確定度: 中）' 固定
]
```

- `Judge` は `PATTERN_RULES` を優先度順（配列順）に評価し、最初にマッチしたルールの `patternId` を返す（§7.2）。
- **`ruleLabel` は必須フィールド**（R3 Major 対応）。印刷詳細モデル §5.2 の `matchedRule.predicateText` は、この `ruleLabel` をそのまま出力する（関数を文字列化して出力しない＝印刷再現性を担保）。
- `patternId` は `PATTERNS` に存在する id であること。**起動時バリデーション**（`AppCore.validate()`）として、(1) `PATTERN_RULES` の全 `patternId` が `PATTERNS` のキー集合に含まれること、(2) 全ルールが `ruleLabel` を保持していることを 1 行チェックし、不整合時はコンソール警告＋splash画面に「設定エラー」バナー表示（開発者が検出可能にする）。

#### 印刷詳細モデル（`printDetailModel`）

詳細版印刷（M-07）の生成元データ構造を本設計で固定する。`Render.toPrint('detail')` は以下のオブジェクトを State と QUESTIONS／PATTERNS から組み立てる。

```
printDetailModel = {
  header: { companyName, date, patternId, patternName },
  answers: [
    { qid, questionText, answerLabel, answerCode, axisContribution /* 例: 'C→2' */ }
    , ... // 回答済み質問のみ。未回答はスキップ
  ],
  matchedRule: { priority, patternId, predicateText /* = PATTERN_RULES[matched].ruleLabel（§5.2.2）。関数の文字列化ではなく ruleLabel を必ず参照する */ },
  checkList: [
    { category, item, status /* '推奨' | '要確認' | '要ヒアリング' */ }
    , ... // パターンの detail（組織/承認/権限/プロジェクト/法/拡張）から展開
  ],
  hearingTags: [ '要ヒアリング: Q12（わからない）', ... ],
  salesMemo: '...',  // S-07 営業メモ。詳細版印刷時のみ最終ブロック。**デフォルト非印字**（匿名化トグルON時）。明示的に「営業メモを印字する」サブトグルONのときのみ印字。空文字時も非表示（§9.3.1）
  disclaimer: '本ツールは診断補助であり、法令判定ではありません。…'
}
```

- `answers` / `checkList` は詳細版の必須列。列仕様がズレない基準として本モデルを参照する。

### 5.3 状態スキーマ（`State.current`）

```
{
  mode: 'splash' | 'full' | 'short',
  persistMode: 'none' | 'local',       // M-11: デフォルト 'none'
  screen: 'splash' | 'question' | 'result' | 'print',
  answers: { Q1:'YES', Q2:'NO', ... },
  history: [ qid, qid, ... ],          // 戻るボタン用
  currentQid: 'Q3',
  pii: { companyName:'', date:'' },  // 任意、デフォルト空（M-13）
  salesMemo: '',  // S-07 営業担当者向けメモ。PII同等扱い（localStorage 保存対象外、§5.4／§9.3.1）
  startedAt: 1713..., completedAt: null,      // KPI計測用
  result: null | {...},
  ui: { printMode: 'summary' | 'detail', localStorageWarning: false },
}
```

### 5.4 localStorage レイアウト（保存モード時のみ）

- キー名: `cs_yesno_diag_v1`（1キーのみ、JSON文字列）
- 内容: `State.current` から `answers` / `history` / `mode` / `currentQid` のみ抽出し保存。**`pii` および `salesMemo` は保存対象から除外**（§9.3 の PII 最小化方針）。
- **保存しないモード時は本キーが絶対に書かれないこと**をコードレビューの観点とする（§9.1）。

---

## 6. インタフェース設計

> 本プロジェクトはCLIを持たない単一HTMLアプリのため、テンプレートの「CLI体系」セクションを **画面体系** に置き換える。

### 6.1 画面体系

| 画面ID | 用途 | 主要UI要素 | 遷移元→先 |
|--------|------|------------|-----------|
| **splash** | 起動時トップ | タイトル／免責／「ショート版開始」「フル版開始」／保存モード選択モーダル（初期「保存しない」） | （起動）→ question |
| **question** | YES/NO・3〜4択の回答画面 | 進捗バー（「回答済/到達予定」表示。§7.1.1 の母数定義参照）／質問文／選択肢ボタン／「これはどういう意味？」展開／戻るボタン | splash→question→…→result |
| **result** | 診断結果カード | パターン名（色分け）／該当理由／推奨設定サマリ／要ヒアリングタグ／工数／注意点／**営業メモ欄（S-07、textarea、任意入力）**／印刷2種ボタン／やり直し／保存クリア | question → result |
| **print** | 印刷プレビュー（要約/詳細） | A4縦レイアウト／ヘッダー（企業名・日付／匿名化ON時は伏せ字）／免責文／印刷トリガ。詳細版は §5.2 `printDetailModel` に準拠 | result ⇄ print |

### 6.2 画面遷移図

```
 splash ──(開始)──▶ question ──(回答完了)──▶ result ──(印刷)──▶ print
   ▲                    │  ▲                   │ ▲                │
   │                    └──┘(戻る)             │ │(やり直し)      │
   │                                           │ └────────────────┘
   └──────────────────────────────(やり直し)───┘
```

### 6.3 状態遷移の責務
- 画面切替は `Render.show(screenId)` のみが行う（直接DOM操作を他モジュールから行わない）。
- 「戻る」（M-03）は `Flow.back()` が `history` 配列からpopし、`State.answers` の該当qidを未回答に戻す。
- 印刷2モード（M-07）は `State.ui.printMode` のフラグで切替え、同じprint画面のCSSクラスで見た目を切り替える。

### 6.4 ファイルI/O
- 読込: なし（全データをJS内定数として内包、オフライン動作 M-10）。
- 書込: localStorage のみ（保存モード時）。ファイルシステム書込はしない。
- 印刷: `window.print()` を呼び、ブラウザ既定のPDF保存／物理印刷に委ねる。

### 6.5 キーボード操作（SHOULD）
- `Y` / `N` キーで YES/NO 回答
- `←` で前の質問に戻る
- `Enter` で選択肢のフォーカス送信

---

## 7. アルゴリズム設計

### 7.1 質問フローエンジン（Flow）

#### フル版（分岐ツリー走査：Flow は DOM非依存ロジック層、戻り値で通知のみ）

```
function next():
  nextQid = QUESTIONS[currentQid].branch(State)
  if nextQid is null:
    return {done: true}            // AppCore が Judge.evaluate() を呼ぶ
  history.push(currentQid)
  currentQid = nextQid
  return {nextQid: nextQid}        // AppCore が Render.show('question') を呼ぶ
```

#### ショート版（線形配列）

```
shortRoute = ['Q2','Q3','Q5','Q12','Q13','Q6','Q15']  // §10.3.5
function next():
  if index+1 >= shortRoute.length:
    return {done: true}
  index++
  history.push(currentQid)
  currentQid = shortRoute[index]
  return {nextQid: currentQid}
```

> **責務分離のルール**: `Flow.next()` / `Flow.back()` は **State を読み／書き**するが、`Judge` も `Render` も呼ばない。判定の起動と画面切替は **AppCore** が戻り値を見て行う（§2.2, §3.2）。

#### 戻る（M-03）

```
function back():
  if history.length === 0:
    return {noop: true}           // 初問では何もしない（AppCore 側でボタン disabled と整合）
  prev = history.pop()
  delete State.answers[currentQid]  // 未回答に戻す
  currentQid = prev
  return {prevQid: prev}

function canGoBack():
  return history.length > 0
```

- 初問（`history.length===0`）では **戻るボタンを disabled にし、キーボード `←` ショートカットも no-op** とする。
- AppCore は `Flow.canGoBack()` の真偽を Render に渡し、Render はその値でボタン属性を決定する。
- 戻る後、進捗バー（§7.1.1）は再計算される（`history.length + 1 + estimateRemaining`）。

#### 7.1.1 進捗バーの母数定義（M-02）

分岐型フル版では「全質問数」が確定しないため、進捗表示は **「回答済/到達予定」** 方式を採用する。

- **ショート版**: 母数は固定 `7`（`shortRoute.length`）。分子は回答済み件数。
- **フル版**: 母数は **現時点の到達予定数** = `history.length + 1（現在質問） + estimateRemaining(State)`。`estimateRemaining` は `branch` 関数を **現在の回答で再走査** し、末端（null）までのルート長を返すヘルパ。回答が変わるたび再計算されるため、進捗バーは多少伸縮し得るが、常に「残り見込みの正直な値」を示す。
- **`estimateRemaining` 実装規約**（R3 Major 対応、実装者ごとのブレ防止）:
  1. 現在の `currentQid` を起点に、`QUESTIONS[qid].branch(State)` を順次呼ぶ。`State` は現時点のもの（回答済み/未回答が混在）をそのまま渡す。
  2. **未回答分岐の既定値は「最短ルート側」固定**（＝残数が最も少なく見える側ではなく、`branch` 関数が未回答（`undefined`）時に返す既定遷移。QUESTIONS 側の `branch(state)` は未回答時に既定 qid を返すよう実装し、`estimateRemaining` 側で選択肢を勝手に仮定しない）。
  3. ループ検出: 同一 qid を2回踏んだら打ち切り（0返却）。`MAX_DEPTH = QUESTIONS.length` として安全弁。
  4. 返り値は**現在質問を含まない残件数**（=呼出側で `+1` する想定）。
  5. テストケース（設計書添付・実装時に自動テスト化すること）:
     - **T1**: ショート版（`mode='short'`）では `estimateRemaining` は呼ばれない。
     - **T2**: フル版・初回（`currentQid='Q1'`、`answers={}`）→ 既定分岐の末端まで辿った長さ（例: `Q1→Q2→Q3→...→Q15` のルート）。
     - **T3**: Q1=YES 回答直後（`currentQid` が次の質問、`Q1='YES'` セット済み）→ T2 より1短い値を返すこと。
- 表示: `3 / 10` のような分数表記を基本とし、パーセントは分子／分母から算出。
- **UI文言は「回答済/到達予定」で固定**（「全質問数」表記は使わない）。要件 M-02「進捗表示」は分岐型であることを前提とし、本アプリでは「到達予定数は回答によって変動し得る」旨のツールチップを進捗バーに常設する（要件解釈の注記）。

### 7.2 判定エンジン（Judge）疑似コード

```
function evaluate(answers, mode):
  // 1. スコア算出（L/A はモード共通、C/P はモード別関数に分離）
  L = calcL(answers)                    // Q2/Q4 から
  A = (mode === 'short') ? calcAShort(answers) : calcAFull(answers)
  C = (mode === 'short') ? calcCShort(answers) : calcCFull(answers)
  P = (answers.Q1==='YES') ? 'FINE' : 'COARSE'
  flags = calcFlags(answers)            // Q6=NO → proxyApprovalMissing 等

  // 2. 決定表を優先度順に評価（§10.3.2、PATTERN_RULES 単一ソース §5.2.2）
  for rule in PATTERN_RULES (priority 1..5):
    if rule.predicate({L,A,C,P,flags,answers}):
      return {pattern: rule.patternId, priorityMatched: rule.priority, ...}

  // 3. フォールバック（優先度6）
  return {pattern: nearestPattern({L,A,C}), priorityMatched: 6, fallback: true,
          tags: [...existing, '要ヒアリング（確定度: 中）']}
```

- **モード分岐は `evaluate` の冒頭のみ**。`PATTERN_RULES` 本体はモードを意識しない（ルール二重化を避ける）。
- ショート版固有の減算（Q7未回答時の A デフォルト、C=3 を発火させない等）は `calcAShort` / `calcCShort` に閉じ込める。

### 7.3 スコア計算ルール詳細（要件§10.3.1 より）

| 軸 | 関数 | 計算 |
|----|------|------|
| **L** | `calcL` | `Q2=YES → 3` / `Q2=NO かつ Q4=YES → 2` / `ELSE → 1`（フル・ショート共通） |
| **A（フル版）** | `calcAFull` | 初期A=1。`Q3=YES → A=max(A,2)`。`Q5=YES かつ L>=2 → A=max(A,2)`。`Q7=YES → A=1`（明示的に1段階） |
| **A（ショート版）** | `calcAShort` | `calcAFull` のうち Q5/Q7 を省略。`Q7` 未回答時は `A=(Q3==='YES')?2:1` を既定値とする |
| **C（フル版）** | `calcCFull` | 初期C=1。`Q12=YES → C=max(C,2)`。`Q17=PART → C=max(C,2)`。`Q16=NOT_READY OR Q17=NOT_READY OR Q6=NO → C=3`。`Q13=UNKNOWN`はCを変えず要ヒアリングタグのみ |
| **C（ショート版）** | `calcCShort` | `Q12=YES → C=max(C,2)`、`Q12=UNKNOWN → C=max(C,2)`、`Q13=UNKNOWN`は変えず要ヒアリングタグのみ。**Q16/Q17 非対応のため C=3 は発火しない**（ショート版ではパターンE確定なし） |
| **P** | `calcP` | `Q1=YES → 'FINE'` / `ELSE → 'COARSE'`（内部コードは英字、表示ラベルは「細/粗」は §10.2 ルールに従い表示層で日本語化） |
| **フラグ** | `calcFlags` | `Q6=NO → flags.proxyApprovalMissing=true`（A/C に影響せず、要ヒアリングタグ発火のみ） |

### 7.4 タイブレーク
- 決定表は優先度順（C軸 > L軸 > A軸）で配列化済み。**先頭から最初にマッチしたものを採用** するだけで優先順位成立（§10.3.3）。
- 副次マッチは結果カードの「該当理由」欄に追記（例「主: E 法対応要整備型 / 副: 多拠点＋拡張計画ありの特徴あり」）。

### 7.5 「わからない」の扱い
- Q12 `わからない`: Cを上げる側に寄せる（ショート版は C=2）、`要ヒアリング: Q12` タグ
- Q13 `未確定`: C変えず、`要ヒアリング: Q13` タグ、印刷時は「労使協定/均等均衡 双方テンプレ併置」
- Q16/Q17 `わからない`: 未整備と同等に扱い C=3 発火、`要ヒアリング` タグ
- Q17 `一部のみ`: C=2、`要ヒアリング` タグ、パターンEの副次判定候補

### 7.6 計算例（要件§6.1 シナリオA再現）
```
入力（内部コード値）: Q2=YES, Q3=YES, Q5=YES, Q12=YES, Q13=KYOTEI, Q6=NO, Q15=YES（mode='short'）
→ L=3, A=calcAShort=2, C=calcCShort=2（Q12=YES で C=2。Q6=NO はフラグのみ。Q16/Q17 非対応のためショート版では C=3 発火せず）
→ 決定表：優先度1（E, C===3）不該当、優先度2（L===3 AND A>=2 AND Q15==='YES'）→ **C: 将来拡張対応型**
→ タグ: 「要ヒアリング: 代理承認未整備（Q6）」「要ヒアリング（省略項目あり）: Q16/Q17等」
```
要件記載の期待結果と一致。

---

## 8. エラーハンドリング・異常系設計

### 8.1 エラー分類

| 区分 | 内容 | 挙動 |
|------|------|------|
| **致命** | JS実行不能／QUESTIONS定数破損 | スプラッシュで「ご利用のブラウザで動作できません」表示、他機能停止 |
| **警告** | localStorage 不可／clipboard 不可／印刷呼出失敗 | 画面上部バナー／フォールバックUI、機能継続 |
| **情報** | 戻る操作、やり直し、保存クリア | トースト風の軽表示（消える） |

### 8.2 具体の挙動

| シナリオ | 挙動 |
|---------|------|
| `localStorage` 例外 | Persist.isAvailable() が false を返す→Stateに `ui.localStorageWarning=true` をセット→Renderが画面上部に黄バナーで「保存機能は無効です。セッション中のみ回答保持」表示 |
| 未定義qidへの遷移 | `console.warn`（devのみ）／UI上はsplashへフォールバック |
| フォールバック判定（優先度6） | 結果カードに「要ヒアリング（確定度: 中）」**黄色バッジ**（要ヒアリングタグは常に黄色で統一。重大度は文言「確定度: 中」で区別）、推奨は最近傍パターンを流用 |

### 8.3 回復可能／不可能の判断
- **回復可能**: ストレージ不可／印刷失敗／判定フォールバック → 機能継続
- **回復不可能**: JS停止／DOM破壊 → 画面リロード案内

### 8.4 ログ
- 本番配布時は `console.*` 出力なし（最小化）。開発フラグ（`DEBUG=true` をコード内で切替）時のみ `console.log` が出る設計。

---

## 9. セキュリティ・プライバシー設計

### 9.1 保存しないモード（デフォルト、M-11）
- スプラッシュ画面のモーダルで `persistMode` を明示選択させ、**初期フォーカスは「保存しない」に固定**。
- `persistMode === 'none'` の間、`Persist.save()` は内部ガード `if (persistMode!=='local') return;` で**一切書き込まない**。
- **モードトグル時の即時保存（R3 Major 対応）**: `none → local` への切替時、AppCore は **切替直後に `Persist.save(State.snapshot())` を1回必ず呼ぶ**。これにより、切替直後にユーザーがブラウザを閉じても（それまでの回答が）復元可能になる。切替前のセッションメモリは保持される。逆方向 `local → none` への切替時は `Persist.clear()` を呼び、既存キーを削除する（保存しないモードへ戻した意図を尊重）。

#### 9.1.1 `Persist.load()` の実行条件（起動時の自動復元禁止）

共有PCでの自動復元による漏えいを防ぐため、`Persist.load()` は **起動時には絶対に呼ばない**。以下の状態遷移のみで復元を許可する。

```
[起動]
  └─▶ splash（persistMode='none' 初期）
         │
         ├─(A)「保存しない」選択 + 「ショート版/フル版 開始」
         │     → State.reset() の新規セッションで question へ。load() 呼ばない。
         │
         ├─(B)「保存する」選択のみ
         │     → persistMode='local' に切替。load() は**まだ呼ばない**。
         │       スプラッシュに「続きから再開」ボタンが出現（既存キー検出時のみ）。
         │
         └─(C)「保存する」+「続きから再開」の2アクション明示
               → Persist.load() 実行 → State へ復元 → 中断位置の question を表示。
```

- 要点: **load() は (C) パターンでのみ発火**。`persistMode='local'` だけでは復元しない。
- スプラッシュ以外の画面から load() を呼ぶ経路は設計上存在しない（Render/Flow は save のみ使用）。
- 既存キー検出のための軽量な `Persist.hasSavedSession()`（キーの存在チェックのみ、内容は読まない）は許可。

### 9.2 localStorage 関連
- 保存モード時でも、キーは **1つだけ**（`cs_yesno_diag_v1`）。
- 保存クリアボタン（M-12）は結果画面・画面右上メニューの2箇所に配置し、`Persist.clear()` + `State.reset()` を呼ぶ（独立した設定画面は用意しない。画面体系§6.1に準拠）。
- ストレージ不可環境では警告バナー表示のうえセッション継続。

### 9.3 PII最小化（M-13）
- S-05 の企業名／担当者名／日付入力欄は **任意・デフォルト空欄**。
- 入力欄の隣に「この情報はブラウザ内のみに残ります」を常時表示。
- 画面共有時のPII露出を避けるため、`pii` フィールドは結果画面ではヘッダーに小さく表示のみ（カード中央の大見出しには使わない）。

#### 9.3.1 デモモードでの PII 取り扱い（実データ投入抑止）

- **デフォルトは PII 入力欄を非表示**。結果画面／印刷プレビューの「企業名等を入力する」トグル（閉じた状態が既定）を明示ONにしたときだけ入力欄を表示する。
- 表示された入力欄は画面上では **マスキング表示**（例: `株式会社●●●`）を基本とし、編集フォーカス時のみ平文表示。印刷プレビューにも「匿名化して印刷」トグル（デフォルト **ON**）を配置する。
- **匿名化トグル（デフォルト ON）の適用範囲**（R3 Critical 対応）: ON の間、`companyName` / 担当者名 / `salesMemo` の3項目すべてをヘッダー/本文ともに伏せ字化する。具体的には、
  - `companyName` / 担当者名: ヘッダーで伏せ字化（例: `株式会社●●●`）。
  - `salesMemo`: **デフォルトは詳細版印刷でも非印字**。印刷時に **明示的に「営業メモを印字する」サブトグルを ON** にした場合のみ、詳細版最終ブロックに印字する。画面上も salesMemo 欄は §9.3.1 の PII 入力欄マスキングと同等の扱い（通常マスク、編集フォーカス時のみ平文）とする。
- **`pii` は `localStorage` 保存対象から除外**（§5.4）。ブラウザ残存リスクを原理的に排除する。
- **`salesMemo`（S-07 営業メモ）も PII 同等扱い**。画面入力位置は結果画面下部の textarea（任意入力・デフォルト空）、印刷出力位置は **詳細版（M-07詳細）の最終ブロックのみ、かつ匿名化トグルOFFまたは「営業メモを印字する」サブトグル明示ONのときだけ**（要約版には出さない）。`localStorage` 保存対象からは除外し、セッションメモリのみで保持する。
- 以上により、「注意書き依存」ではなく構造的に実データ投入を抑止する（`salesMemo` もデフォルトで印字されない＝PII抑止を設計で完結）。

### 9.4 免責文の常時表示（M-14）
- `#app-header` に固定（`position: sticky; top:0;`）し、**画面表示時は全画面（splash/question/result/print）で常時表示**。
- 文言: 「本ツールは診断補助であり、法令判定ではありません。最終判断は専門家レビューを前提とします」。
- **印刷時は `position: sticky` を使わない**。`@media print` で `#app-header` は `position: static;` に戻し、**各ページヘッダーには印刷専用の免責要素**（`.disclaimer-print`、`thead` ／ `running header` 相当のブロック）を別実装で出力する（要約版・詳細版ともに）。sticky のまま印刷すると初頁にしか出ない／重なり切れるブラウザがあるため、両者は別実装である点を明記。

### 9.5 禁止事項（MUST NOT）
- 外部通信（`fetch`/`XMLHttpRequest`/`<img src=外部URL>`/`<link href=外部>`）は禁止。
- 「顧客情報漏洩リスクなし」のような断定表現を画面・説明文に書かない。
- CDN読込・外部フォント読込・Google Fonts等、一切禁止。

### 9.6 オフライン動作（M-10）担保
- HTML内で `http://` `https://` で始まるURLを参照する箇所がないことをビルド（手作業可）時チェック。
- 画像は SVG インライン or CSS 描画のみ。
- ファイルサイズは**目標300KB / 上限1MB**（§5、§7.2）。質問データ・パターン定義・CSSの合計で監視。

---

## 10. 観測可能性・運用設計

### 10.1 ログ出力方針
- 本アプリはサーバレス単一HTMLのため、**永続ログなし**。
- 開発モード時のみ `console.debug` で Flow / Judge の状態遷移を出力（コード内フラグで切替）。
- KPI計測用のみ、`startedAt` / `completedAt` を State に記録し、結果画面に「所要時間: 3分28秒」として表示（要件§8）。起点は **最初に表示した質問の時刻**（ショート版=Q2、フル版=Q1）に統一。

#### 10.1.1 診断サマリコピー（S-04：メール貼付用テキスト主・開発者向けJSON副）

S-04 の要件意図は「メール貼り付け用のサマリコピー」。主用途は営業担当者によるメール共有であり、JSON は二次用途。以下の2ボタン構成に分離する（R2 Major 1対応）。

**(a) 主機能「結果サマリをコピー」（S-04 本体）**

- ボタン位置: 結果画面の目立つ位置（印刷ボタンの隣）。
- 出力形式: **人間可読のプレーンテキスト**（メール本文に貼付できる体裁）。例:
  ```
  【運用整備ナビゲーター 診断結果】
  パターン: C 将来拡張対応型
  該当理由: 多拠点(L=3)／承認2段階以上(A=2)／拡張計画あり(Q15=YES)
  要ヒアリング: 代理承認未整備(Q6)、Q16/Q17 省略
  推奨工数目安: 10〜15営業日
  ---
  本ツールは診断補助であり、法令判定ではありません。
  ```
- 動作: `navigator.clipboard.writeText(...)`。不可時は §4.3 のフォールバック（テキスト選択済みモーダル）に合流。
- PII は含めない（企業名等は匿名化方針に従いヘッダーに入れない）。

**(b) 副機能「診断サマリJSONをコピー」（開発者向けセッション監査）**

- ボタン位置: 結果画面右上の「開発者向け」メニュー配下に格納（通常運用では目立たせない）。
- 出力内容: `{ startedAt, completedAt, mode, answers, result, hearingTags, appVersion }`（PII `pii` は **含めない**）。
- 用途: セミナー後の社内検証・誤判定指摘のエビデンス。ユーザー操作で初めて出力され、ネットワークには出ない。

### 10.2 デモ時の見せ方との整合
- スプラッシュ画面の「ショート版で開始」ボタンをメインCTA（大きめ）にし、セミナー本番は5分で完走できる導線を保証。
- 結果画面の「要ヒアリング」タグは**全ケース黄色バッジで統一**（通常／省略項目／フォールバック＝確定度:中 いずれも黄色。重大度は文言側で区別）。営業が「ここは持ち帰って詳細ヒアリングします」と自然に締められるトリガにする。
- 印刷プレビューは**要約版（A4 1枚）をデフォルト**にして、セミナーでは1クリックで手土産化。

### 10.3 将来拡張への接続点
| 将来要件 | 設計上の配慮 |
|---------|--------------|
| Y-01 URL共有 | State に `serialize()` / `deserialize()` 拡張点を用意。URLハッシュ経由の復元を後付可能な構造 |
| Y-02 ダークモード | CSS 変数（`--bg`, `--fg`, `--accent`）でテーマ定義、bodyクラス切替だけで対応可 |
| Y-03 複数パターン比較 | **拡張時に追加予定**（現行は `PATTERN_RULES` 優先度順の最初マッチのみ。Y-03 実装時に Judge に全パターンのスコア距離算出関数を追加する方針）。現行実装責務には含めない |
| Y-04 業界統計比較 | PATTERNS 定数に `benchmark` フィールドを追加できる構造 |
| Y-05 QRコード | 純JSのQR生成コード（軽量1ファイル版）をインライン追記できる余地。ただしファイルサイズ上限1MB厳守 |
| 質問追加 | QUESTIONS 配列への追加＋`branch` 関数の編集のみで対応。決定表（PATTERN_RULES）とは疎結合 |
| パターン追加 | PATTERNS 配列と PATTERN_RULES への追加のみ |

---

## 付録A. 想定ファイル構造

```
04_yesno-diagnosis/
├── docs/
│   ├── 01_requirements.md       （要件定義書、既存）
│   ├── 02_design.md             （本書）
│   └── context-alignment-notes.md（文脈寄せメモ、既存）
├── src/
│   └── index.html                （唯一の成果物。JS/CSSすべて内包）
└── samples/
    └── demo_answers.json         （開発テスト用の回答セット、配布対象外）
```

配布物は `src/index.html` の**1ファイルのみ**。メール添付・USB・Slack投稿すべて可。

## 付録B. 用語定義（要件定義書§付録から継承）

要件定義書§付録の派遣業界用語（抵触日／3年ルール／同一労働同一賃金／36協定／労使協定方式／均等均衡方式／事業所単位・個人単位の期間制限）をそのまま本設計でも採用する。

## 付録C. 設計上の決定記録

| 決定事項 | 選択肢 | 採用理由 |
|---------|--------|----------|
| 単一HTML内でJSモジュールをどう分割するか | (a) クラスベース, (b) IIFE+名前空間, (c) ES Modules | **(b) IIFE+名前空間**。`file://` で動作させる要件上、ES Modulesは一部ブラウザで制限あり。IIFEなら確実 |
| 状態管理ライブラリ | (a) 自作Stateオブジェクト, (b) Proxyベース, (c) なし（直接DOM） | **(a) 自作**。小規模かつ外部依存禁止、Proxyは印刷時の変更検知不要のため過剰 |
| 質問定義の形式 | (a) 配列＋branch関数, (b) グラフDSL, (c) JSONステートマシン | **(a)**。保守性とコンパクトさのバランス。将来質問追加時の変更点が最小 |
| 保存モード初期値 | (a) 保存しない, (b) 保存する, (c) 前回値を継承 | **(a)**。M-11「安全側デフォルト」をUIレベルで担保 |
| 印刷2モード実装方式 | (a) 別画面, (b) 同一HTMLをCSSクラスで切替, (c) 別window | **(b)**。コード量最小、@media print で一体管理可能 |
| フォールバック時のパターン算出 | (a) 常にA, (b) 最近傍, (c) エラー表示 | **(b) 最近傍**。要件§10.3.2 優先度6 に準拠、デモ映えを損なわない |

---

**以上**
