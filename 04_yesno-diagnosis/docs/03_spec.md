# 技術仕様書: 運用整備状況 簡易診断アプリ（04_yesno-diagnosis）

> 本書は要件定義書 `01_requirements.md` および設計書 `02_design.md` を受けて、**実装直前の具体形**（DOM骨格、関数シグネチャ、データスキーマ、判定ロジックの near-JS 疑似コード、テストケース）を定義する。本書を読めば Phase5 実装者が迷わず index.html を書き始められる粒度に仕上げている。

---

## 1. 仕様書の位置付け

### 1.1 要件定義書・設計書との対応
| 上位ドキュメント | 本仕様書での受け |
|------------------|------------------|
| 要件§1.5（単一HTML）／§5（非機能）／§7.2（制約） | §2 動作環境 / §3 ファイル構成 |
| 要件§4 機能要件 M-01〜M-14 | §7 DOM骨格 / §8 JS モジュール仕様 / §9 エラー処理 / §11 プライバシー |
| 要件§10 質問フロー（含 §10.3 決定表・§10.3.5 ショート版） | §4 質問データ / §5 パターンルール / §6 判定アルゴリズム |
| 要件§11 運用パターン | §5 PATTERNS 定義 |
| 設計§2〜3 アーキテクチャ／モジュール | §8 JS モジュール仕様 |
| 設計§5 データモデル | §4 データスキーマ実装版 |
| 設計§7 アルゴリズム | §6 判定アルゴリズム近似コード |
| 設計§9 プライバシー | §11 プライバシー実装詳細 |

### 1.2 カバー範囲
- 動作環境、単一HTMLのファイル内部構成、DOM骨格サンプル
- JSモジュールの関数シグネチャと状態スキーマ
- 質問データ（Q1〜Q17 完全版＋ショート版7問）の実装用定数
- `PATTERN_RULES` 配列の完全定義（predicate 関数付き）
- 判定エンジン（L/A/C/P軸スコア、決定表、タイブレーク、フォールバック）
- 印刷CSS方針、ARIA属性方針、テスト設計

### 1.3 カバーしない範囲
- 最終CSSの色値・余白のピクセル確定（§10 に基準のみ）
- 質問文の最終コピーライティングレビュー（文言は要件§10.2のものをそのまま採用）
- セミナー配布パッケージング（zip化、README文面）
- 実クラウドスタッフィング画面との連携（スコープ外）

### 1.4 実装着手の前提条件
- 設計書までの3往復 Codex レビューが完了していること（済）
- 本仕様書で定義する QUESTIONS / PATTERNS / PATTERN_RULES をそのまま JS 内定数としてハードコードすること
- 実装物理ファイルは `src/index.html` 1本のみ

---

## 2. 動作環境と依存

### 2.1 対応ブラウザ
| ブラウザ | 最低バージョン | 備考 |
|----------|-------------|------|
| Google Chrome | 120+ | メイン動作保証 |
| Microsoft Edge | 120+ | Chromium 系、Chrome と同等 |
| Apple Safari | 17+ | macOS 14 以降想定 |
| Mozilla Firefox | 120+ | file:// での localStorage 動作前提 |

- IE / 旧 Edge (Legacy) は MUST NOT 対象。
- モバイル Safari / Chrome Android は動作すれば OK（非保証、SHOULD）。

### 2.2 動作形態
- **`file://` プロトコル完全動作保証**（ダブルクリック起動）。
- HTTP サーバ不要、ビルド不要、インストール不要。
- オフライン（ネット切断）で全機能動作（要件 M-10）。

### 2.3 外部依存
- **外部CDN・外部フォント・外部画像 禁止**（要件§5／§7.2）。
- 使用可能な内蔵機能: `localStorage`, `window.print()`, `navigator.clipboard`（使えない環境はフォールバック）。
- JavaScript ライブラリ・フレームワーク一切禁止（Vanilla JS のみ）。
- Python／npm 等のライブラリ・バージョン固定は **N/A**（Vanilla JS・外部依存ゼロ・単一 HTML 完結のため、依存解決も `package.json` / `requirements.txt` も存在しない。mS-R2-3）。

### 2.4 ファイルサイズ
- **目標 300KB / 上限 1MB**（メール添付想定、要件§5／§7.2）。
- 実装時は `ls -l src/index.html` で定期チェック。画像は SVG インラインまたは CSS 描画のみ。

### 2.5 文字コードとロケール
- `<meta charset="UTF-8">` 固定。
- 日本語表示のみ。`lang="ja"` を `<html>` に付与。

---

## 3. ディレクトリ構成（実装版）

```
04_yesno-diagnosis/
├── docs/
│   ├── 01_requirements.md       （要件定義書）
│   ├── 02_design.md             （設計書）
│   ├── 03_spec.md               （本書）
│   └── context-alignment-notes.md
├── src/
│   └── index.html               ← 唯一の配布物。JS/CSS 全内包
└── samples/
    └── demo_answers.json        （開発時テスト用、配布対象外）
```

### 3.1 開発時の運用方針（任意）
- `src/index.html` は 1 ファイル配布だが、開発の見通しのため「src_draft/」下で `index.html` / `styles.css` / `app.js` に分けて書き、**手動で `<style>`／`<script>` に埋め込んで index.html に結合**してもよい。
- ただし自動ビルドスクリプトは用意しない（最小実装方針）。最終成果物は必ず単一ファイルである点のみ守る。

---

## 4. データスキーマ（実装レベル）

### 4.1 回答値のコード統一

内部処理はすべて**英字コード値**、日本語は表示レイヤのみで扱う（設計§5.2 / §7.3）。

```js
// 回答値の正規コード
const ANS = Object.freeze({
  YES: 'YES',
  NO: 'NO',
  UNKNOWN: 'UNKNOWN',       // Q12「わからない」
  KYOTEI: 'KYOTEI',         // Q13 労使協定方式
  KINTOU: 'KINTOU',         // Q13 均等均衡方式
  UNDECIDED: 'UNDECIDED',   // Q13 未確定
  SELF_RUN: 'SELF_RUN',     // Q16 自社運用
  OUTSOURCED: 'OUTSOURCED', // Q16 顧問社労士委託
  NOT_READY: 'NOT_READY',   // Q16/Q17 未整備
  DEFINED: 'DEFINED',       // Q17 定めている
  PART: 'PART',             // Q17 一部のみ
});
```

### 4.2 質問定義（`QUESTIONS` 辞書スキーマ）

```js
/**
 * @typedef {Object} Question
 * @property {string} id              - 'Q1'〜'Q17'（Q11 欠番）
 * @property {string} text            - 表示文（要件§10.2 準拠）
 * @property {'YN'|'MULTI'} type      - YN=2択, MULTI=3/4択
 * @property {{value:string,label:string}[]} choices - 2〜4 件
 * @property {(state:State)=>string|null} branch    - フル版の次QID or null（完了）
 * @property {string[]} axis          - 関連評価軸 ['L','A','C','P'] の部分集合
 * @property {string} domain          - 業務領域タグ（例「法対応／契約」）
 * @property {string} hint            - S-01 補足説明
 * @property {(ans:string)=>{needHearing:boolean,reason?:string}} triage - 要ヒアリング判定
 */
```

### 4.3 状態スキーマ（`State.current`）

```js
State.current = {
  mode: 'splash',                          // 'splash'|'full'|'short'
  persistMode: 'none',                     // 'none'|'local'（M-11 デフォルト none）
  screen: 'splash',                        // 'splash'|'question'|'result'|'print'
  answers: {},                             // { [qid]: ANS.* }
  history: [],                             // 戻るボタン用 qid スタック
  currentQid: null,
  shortIndex: 0,                           // ショート版配列インデックス
  pii: { companyName: '', contactName: '', date: '' }, // M-13 デフォルト空欄（companyName/contactName/date の3項目で固定、匿名化・除外対象も同一）
  salesMemo: '',                           // S-07 PII 同等扱い
  startedAt: null,                         // KPI: 最初の質問表示時刻
  completedAt: null,
  result: null,                            // Judge.evaluate の戻り値
  ui: {
    printMode: 'summary',                  // 'summary'|'detail'
    localStorageWarning: false,
    anonymize: true,                       // 匿名化印刷トグル（§11.3 デフォルト ON）
    printSalesMemo: false,                 // 営業メモ印字サブトグル（デフォルト OFF）
    piiFieldsOpen: false,                  // 「企業名等を入力する」トグル（デフォルト閉）
  },
  appVersion: '1.0.0',
};
```

### 4.4 判定結果スキーマ（`result`）

```js
/**
 * @typedef {Object} JudgeResult
 * @property {'A'|'B'|'C'|'D'|'E'} patternId
 * @property {1|2|3|4|5|6} priorityMatched
 * @property {{L:1|2|3, A:1|2|3, C:1|2|3, P:'FINE'|'COARSE'}} scores
 * @property {{proxyApprovalMissing:boolean}} flags
 * @property {string[]} tags                              - 要ヒアリングタグ文字列配列
 * @property {string[]} subMatches                        - 副次マッチルールの ruleLabel 配列
 * @property {ReasonHighlight[]} reasonHighlights         - 該当理由欄の生成元
 * @property {boolean} fallback
 *
 * @typedef {Object} ReasonHighlight
 * @property {'L'|'A'|'C'|'EXT'} axis                     - scores に含まれる軸 + 拡張計画を表す 'EXT'
 * @property {number|string} value                        - 軸が L/A/C の場合は 1|2|3、'EXT' の場合は 'YES' 固定
 * @property {string[]} qids
 */
result = {
  patternId: 'A'|'B'|'C'|'D'|'E',
  priorityMatched: 1|2|3|4|5|6,
  scores: { L: 1|2|3, A: 1|2|3, C: 1|2|3, P: 'FINE'|'COARSE' },
  flags: { proxyApprovalMissing: false },
  tags: [],                                // 要ヒアリングタグ文字列配列
  subMatches: [],                          // 副次マッチルールの ruleLabel 配列
  reasonHighlights: [                      // 該当理由欄の生成元（axis は 'L'|'A'|'C'|'EXT'）
    { axis: 'L', value: 3, qids: ['Q2'] },
    { axis: 'EXT', value: 'YES', qids: ['Q15'] }, // 'EXT' は scores には含まれず reasonHighlights 専用
    // ...
  ],
  fallback: false,
};
```

### 4.5 localStorage レイアウト（保存モード時のみ）

- キー: `cs_yesno_diag_v1`（1 キーのみ）
- 値: JSON 文字列
- **保存対象**: `answers`, `history`, `mode`, `currentQid`, `shortIndex`, `appVersion`, `persistMode`
  - `persistMode` も保存対象（load() 復元後の保存再開を保証するため。CS-R1-2 対応）
- **保存除外（PII）**: `pii`, `salesMemo`, `startedAt`, `completedAt`, `ui`（設計§5.4 / CS-R1-5）
- **`appVersion` 非互換時ポリシー**: 本アプリは `appVersion='1.0.0'`（v1 系）固定。将来 v2 以降を導入する場合、読み込み時に `appVersion` が v1 系でなければ**旧データを破棄**して `splash` に戻す（移行処理は実装しない、mS-R1-3）。

```json
{
  "appVersion": "1.0.0",
  "mode": "short",
  "persistMode": "local",
  "currentQid": "Q13",
  "shortIndex": 4,
  "answers": { "Q2":"YES", "Q3":"YES", "Q5":"YES", "Q12":"YES" },
  "history": ["Q2","Q3","Q5","Q12"]
}
```

---

## 5. 質問データ実装用完全定義

### 5.1 QUESTIONS 辞書（ID キー、Q1〜Q17、Q11 欠番）

`QUESTIONS` は ID をキーとする**辞書オブジェクト**（配列ではない）。分岐関数から `QUESTIONS[nextQid]` で直接参照するため辞書形式を採用（付録B 決定記録）。実装者はそのまま index.html の `<script>` 内にコピーして使うこと。`branch` 関数のロジックは要件§10.1 の分岐ツリーを忠実に反映。

```js
const QUESTIONS = {
  Q1: {
    id: 'Q1',
    text: '派遣スタッフの就業先は、複数の派遣先事業所にまたがりますか？',
    type: 'YN',
    choices: [{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch: (s) => 'Q2',
    axis: ['P'],
    domain: '発注／契約',
    hint: '派遣先の事業所単位で抵触日が管理されるため、複数事業所への派遣がある場合は登録粒度を細かくする必要があります',
    triage: () => ({needHearing:false}),
  },
  Q2: {
    id:'Q2',
    text:'派遣元として、拠点（営業所・支社）は3箇所以上ありますか？',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> s.answers.Q2===ANS.YES ? 'Q3' : 'Q4',
    axis:['L'],
    domain:'データ運用',
    hint:'拠点数が多いほど組織ツリーを深く切り、案件・勤怠・請求データに対する権限設定が複雑になります',
    triage: () => ({needHearing:false}),
  },
  Q3: {
    id:'Q3',
    text:'拠点ごとに、契約・勤怠・請求を承認する営業所長などの承認者がいますか？',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> s.answers.Q3===ANS.YES ? 'Q5' : 'Q6',
    axis:['A'],
    domain:'契約／勤怠／請求',
    hint:'拠点単位の承認者がいる場合、承認ルートを「拠点→本社」の2段階以上で設計します',
    triage: () => ({needHearing:false}),
  },
  Q4: {
    id:'Q4',
    text:'本社以外に、案件管理・請求処理などの実質的な管理機能を持つ拠点はありますか？',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> s.answers.Q4===ANS.YES ? 'Q5' : 'Q7',
    axis:['L'],
    domain:'案件／請求',
    hint:'管理機能がある拠点は、マスタ編集権限やレポート閲覧範囲を個別設定します',
    triage: () => ({needHearing:false}),
  },
  Q5: {
    id:'Q5',
    text:'本社で全拠点の案件・勤怠・請求・評価を一元管理したいですか？',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> s.answers.Q5===ANS.YES ? 'Q6' : 'Q8',
    axis:['A'],
    domain:'案件／勤怠／請求／評価',
    hint:'一元管理型の場合、本社管理部門に全拠点横断の閲覧権限を付与します',
    triage: () => ({needHearing:false}),
  },
  Q6: {
    id:'Q6',
    text:'承認者が不在時、契約・勤怠・請求の代理承認ルートを決めていますか？',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> 'Q9',
    axis:['C'],
    domain:'契約／勤怠／請求',
    hint:'未整備の場合、導入時に代理承認フローの設計が別途必要になります',
    triage:(a)=> a===ANS.NO ? {needHearing:true,reason:'代理承認ルート未整備（Q6）'} : {needHearing:false},
  },
  Q7: {
    id:'Q7',
    text:'承認は1段階（直属上司のみ）で十分ですか？',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> s.answers.Q7===ANS.YES ? 'Q10' : 'Q9',
    axis:['A'],
    domain:'契約／勤怠',
    hint:'小規模事業者は1段階承認でOK。ただし内部統制上は2段階推奨',
    triage: () => ({needHearing:false}),
  },
  Q8: {
    id:'Q8',
    text:'拠点間で給与・勤務ルール（勤怠締め・時給体系など）は異なりますか？',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> 'Q10',
    axis:['L'],
    domain:'勤怠／請求',
    hint:'異なる場合、拠点ごとに給与テンプレート・勤務マスタを分けて登録します',
    triage: () => ({needHearing:false}),
  },
  Q9: {
    id:'Q9',
    text:'派遣先からの勤怠承認を電子化したいですか？',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> 'Q10',
    axis:[],
    domain:'勤怠',
    hint:'電子化する場合、派遣先担当者のアカウント発行と承認権限設定が必要です',
    triage: () => ({needHearing:false}),
  },
  Q10: {
    id:'Q10',
    text:'職種別に給与テーブルを分けていますか？（請求単価にも影響する観点）',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> 'Q12',
    axis:['C'],
    domain:'請求／法対応',
    hint:'同一労働同一賃金対応上、職種別テーブルの分離は要検討事項です',
    triage: () => ({needHearing:false}),
  },
  // Q11 は欠番（要件§10.2 で Q10 に統合済み）
  Q12: {
    id:'Q12',
    text:'同一派遣先での継続派遣が3年（抵触日）を超える可能性のある案件を扱っていますか／扱う予定ですか？',
    type:'MULTI',
    choices:[
      {value:ANS.YES,label:'はい'},
      {value:ANS.NO,label:'いいえ'},
      {value:ANS.UNKNOWN,label:'わからない'},
    ],
    branch:(s)=> 'Q13',
    axis:['C'],
    domain:'法対応／契約',
    hint:'派遣法上の抵触日の管理対象となり得る案件の有無を確認します。本アプリでは抵触日管理は原則ON前提',
    triage:(a)=> a===ANS.UNKNOWN ? {needHearing:true,reason:'Q12（抵触日対象案件：わからない）'} : {needHearing:false},
  },
  Q13: {
    id:'Q13',
    text:'同一労働同一賃金対応の方式は確定していますか？',
    type:'MULTI',
    choices:[
      {value:ANS.KYOTEI,label:'労使協定方式'},
      {value:ANS.KINTOU,label:'均等均衡方式'},
      {value:ANS.UNDECIDED,label:'未確定'},
    ],
    branch:(s)=> 'Q14',
    axis:['C'],
    domain:'法対応／請求',
    hint:'方式未確定の場合は双方の初期設定を提示し「顧客の労務担当と確認要」と注記します',
    triage:(a)=> a===ANS.UNDECIDED ? {needHearing:true,reason:'Q13（同一労働同一賃金：未確定）'} : {needHearing:false},
  },
  Q14: {
    id:'Q14',
    text:'同一人物が複数拠点・複数部署を兼任する運用はありますか？',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> 'Q15',
    axis:[],
    domain:'契約／データ運用',
    hint:'兼務ユーザーは複数組織への所属許可と権限の論理和制御が必要です',
    triage: () => ({needHearing:false}),
  },
  Q15: {
    id:'Q15',
    text:'今後1年以内に、拠点追加・M&A・事業拡大の計画はありますか？',
    type:'YN',
    choices:[{value:ANS.YES,label:'はい'},{value:ANS.NO,label:'いいえ'}],
    branch:(s)=> s.mode==='short' ? null : 'Q16',
    axis:[],
    domain:'データ運用',
    hint:'拡張計画がある場合、組織コード体系を拡張に耐える桁数で設計します',
    triage: () => ({needHearing:false}),
  },
  Q16: {
    id:'Q16',
    text:'36協定（時間外労働上限）の運用はどの体制ですか？',
    type:'MULTI',
    choices:[
      {value:ANS.SELF_RUN,label:'自社運用'},
      {value:ANS.OUTSOURCED,label:'顧問社労士に委託'},
      {value:ANS.NOT_READY,label:'未整備'},
      {value:ANS.UNKNOWN,label:'わからない'},
    ],
    branch:(s)=> 'Q17',
    axis:['C'],
    domain:'法対応／勤怠',
    hint:'36協定の締結・届出は法令上の手続きで本アプリは関与しません。SaaS上での超過監視要件を判定します',
    triage:(a)=> (a===ANS.NOT_READY||a===ANS.UNKNOWN) ? {needHearing:true,reason:'Q16（36協定運用体制）'} : {needHearing:false},
  },
  Q17: {
    id:'Q17',
    text:'抵触日の運用体制（3ヶ月前通知・法務承認等）は定まっていますか？',
    type:'MULTI',
    choices:[
      {value:ANS.DEFINED,label:'定めている'},
      {value:ANS.PART,label:'一部のみ'},
      {value:ANS.NOT_READY,label:'未整備'},
      {value:ANS.UNKNOWN,label:'わからない'},
    ],
    branch:(s)=> null,                    // フル版はここで完了
    axis:['C'],
    domain:'法対応／契約',
    hint:'抵触日管理機能自体はONを前提とし、通知間隔と承認ルート設計の詳細度を判定します',
    triage:(a)=> (a===ANS.PART||a===ANS.NOT_READY||a===ANS.UNKNOWN) ? {needHearing:true,reason:'Q17（抵触日運用体制）'} : {needHearing:false},
  },
};
```

### 5.2 ショート版ルート（設計§7.1）

```js
const SHORT_ROUTE = ['Q2','Q3','Q5','Q12','Q13','Q6','Q15'];
// ショート版では branch 関数を参照せず、配列インデックスで線形に送る。
// mS-R3-1: SHORT_ROUTE は Q1 を含まないため、ショート版は **P 軸（粒度）を未評価とし COARSE 扱い**で確定する（§8.4 `calcP` 参照）。
//   P 軸を真に評価したい場合はフル版（Q1 を含む 15 問）を使うこと。
```

これを含めショート版は要件§6.1 シナリオ A（4 分以内完走）と PATTERN_RULES の A〜E 判定を達成するための**最小質問集合**として設計されている（要件§6.1 / 設計§7.1）。

---

## 6. パターンルール実装用完全定義

### 6.1 PATTERNS（表示情報のみ、要件§11 準拠）

```js
// CS-R2-2: `detail` は詳細版印刷（M-06/M-07）のチェックリスト展開元。
//   各項目は { category, label, status } の 3 列。status は '推奨'|'要確認'|'要ヒアリング' の 3 値。
//   設計§5.2 `printDetailModel.checkList` および §10.3 `PrintChecklistItem` と完全一致させる。
const PATTERNS = {
  A: {
    id:'A', name:'基本整備型', colorVar:'--pattern-a',
    summary5:[
      '組織ツリー: 本社1層のみ（部署マスタ3〜5件）',
      '承認ルート: 直属上司のみ（1段階）',
      '権限: 管理者 / 一般の2ロール',
      '案件紐付け: 全案件が本社所属',
      '抵触日管理: 原則ON・簡易アラート',
    ],
    effort:'2〜3営業日',
    cautions:[
      '成長時の拡張には耐えないため、拠点追加計画があるならパターンBを推奨',
      '抵触日・同一労働同一賃金・36協定の体制整備は小規模でも派遣元として法令上必要',
    ],
    detail:[
      { category:'組織',     label:'本社1層のみ（部署マスタ3〜5件）', status:'推奨' },
      { category:'承認',     label:'直属上司1段階承認', status:'推奨' },
      { category:'権限',     label:'管理者 / 一般の2ロール', status:'推奨' },
      { category:'案件',     label:'全案件を本社所属に紐付け', status:'推奨' },
      { category:'法対応',   label:'抵触日管理ON・簡易アラート', status:'推奨' },
      { category:'法対応',   label:'同一労働同一賃金の方式確定', status:'要確認' },
      { category:'法対応',   label:'36協定の運用体制確立', status:'要確認' },
      { category:'拡張',     label:'拠点追加計画がある場合は B への移行を検討', status:'要ヒアリング' },
    ],
  },
  B: {
    id:'B', name:'複数拠点対応型', colorVar:'--pattern-b',
    summary5:[
      '組織ツリー: 本社 → 営業所の2層',
      '承認ルート: 営業所長 → 本社管理部（2段階）',
      '権限: 拠点別ロール（所長/所員/本社管理/経理）',
      '案件紐付け: 受注拠点所属、横串は担当者で解決',
      '抵触日管理ON・同一労働同一賃金は労使協定方式',
    ],
    effort:'5〜7営業日',
    cautions:['代理承認ルールの未整備が多いため、導入時に必ず整理'],
    detail:[
      { category:'組織',     label:'本社 → 営業所の2層（拠点コード2桁）', status:'推奨' },
      { category:'承認',     label:'営業所長 → 本社管理部（2段階）', status:'推奨' },
      { category:'権限',     label:'拠点別ロール（所長/所員/本社管理/経理）', status:'推奨' },
      { category:'案件',     label:'受注拠点所属、横串は担当者で解決', status:'推奨' },
      { category:'法対応',   label:'抵触日管理ON・同一労働同一賃金は労使協定方式', status:'推奨' },
      { category:'承認',     label:'代理承認ルールの整備', status:'要ヒアリング' },
      { category:'拡張',     label:'今後のエリア統括導入余地', status:'要確認' },
    ],
  },
  C: {
    id:'C', name:'将来拡張対応型', colorVar:'--pattern-c',
    summary5:[
      '組織ツリー: 本社 → エリア統括 → 営業所の3層',
      '承認ルート: 所長→エリア長→本社（最大3段階）',
      '権限: 細粒度ロール7〜10種、横断閲覧は本社職のみ',
      '案件紐付け: 受注拠点×担当拠点の二軸、横串フラグ',
      '拠点コード4桁、階層別プレフィックス体系',
    ],
    effort:'10〜15営業日',
    cautions:['導入プロジェクトとして3ヶ月計画推奨、段階リリース'],
    detail:[
      { category:'組織',     label:'本社 → エリア統括 → 営業所の3層', status:'推奨' },
      { category:'承認',     label:'所長→エリア長→本社（最大3段階）', status:'推奨' },
      { category:'権限',     label:'細粒度ロール7〜10種、横断閲覧は本社職のみ', status:'推奨' },
      { category:'案件',     label:'受注拠点×担当拠点の二軸、横串フラグ', status:'推奨' },
      { category:'データ運用', label:'拠点コード4桁、階層別プレフィックス体系', status:'推奨' },
      { category:'法対応',   label:'抵触日管理ON・同一労働同一賃金方式確定', status:'要確認' },
      { category:'拡張',     label:'3ヶ月計画で段階リリース', status:'要ヒアリング' },
    ],
  },
  D: {
    id:'D', name:'多事業所分散型', colorVar:'--pattern-d',
    summary5:[
      '各拠点を独立事業体として登録（疑似マルチテナント）',
      '承認ルート: 拠点内完結、本社は参照のみ',
      '権限: 拠点長に強め、本社は閲覧限定',
      '案件紐付け: 拠点内完結、横串は原則なし',
      '給与テンプレート: 拠点ごとに分離',
    ],
    effort:'拠点数 × 2営業日',
    cautions:['横串経営レポートにはBI連携が別途必要'],
    detail:[
      { category:'組織',     label:'各拠点を独立事業体として登録（疑似マルチテナント）', status:'推奨' },
      { category:'承認',     label:'拠点内完結、本社は参照のみ', status:'推奨' },
      { category:'権限',     label:'拠点長に強め、本社は閲覧限定', status:'推奨' },
      { category:'案件',     label:'拠点内完結、横串は原則なし', status:'推奨' },
      { category:'勤怠／請求', label:'給与テンプレートを拠点ごとに分離', status:'推奨' },
      { category:'法対応',   label:'拠点ごとの法対応状況の棚卸し', status:'要確認' },
      { category:'拡張',     label:'横串経営レポートの BI 連携', status:'要ヒアリング' },
    ],
  },
  E: {
    id:'E', name:'法対応要整備型', colorVar:'--pattern-e',
    summary5:[
      '組織ツリー: B/C をベース（拠点数・承認は他軸で決定）',
      '承認ルート: 抵触日通知ワークフロー整備を優先',
      '権限: 法務/労務ロールの新設・抵触日限定アクセス',
      '案件紐付け: 派遣法区分（3年ルール対象/除外）を明示',
      '36協定超過監視は体制整備後にON（未整備時は要ヒアリング）',
    ],
    effort:'8〜12営業日（体制整備含む）',
    cautions:[
      '「法対応が強化されている型」ではなく「法対応体制の整備が必要な型」である',
      '派遣法改正時の見直し運用プロセスを別途定義',
    ],
    detail:[
      { category:'組織',     label:'B/C をベースに拠点数・承認を他軸で決定', status:'推奨' },
      { category:'承認',     label:'抵触日通知ワークフローの整備を最優先', status:'推奨' },
      { category:'権限',     label:'法務／労務ロールの新設・抵触日限定アクセス', status:'推奨' },
      { category:'案件',     label:'派遣法区分（3年ルール対象/除外）を明示', status:'推奨' },
      { category:'法対応',   label:'36協定の運用体制（自社／社労士委託）の確定', status:'要ヒアリング' },
      { category:'法対応',   label:'抵触日の運用体制（3ヶ月前通知・法務承認）整備', status:'要ヒアリング' },
      { category:'法対応',   label:'代理承認ルートの未整備解消', status:'要ヒアリング' },
      { category:'法対応',   label:'派遣法改正時の見直し運用プロセスの定義', status:'要確認' },
      { category:'拡張',     label:'体制整備後に 36 協定超過監視 ON', status:'要確認' },
    ],
  },
};
```

### 6.2 PATTERN_RULES 配列（判定単一ソース、設計§5.2.2）

```js
const PATTERN_RULES = [
  {
    priority: 1,
    patternId: 'E',
    // MS-R2-1: 要件§10.3.2 を正として「Q17=一部のみ」も E 条件に含める（C=3 に昇格）。
    //   R1 で暫定的に PART を除外したが、R2 で要件書に揃えて再反転。
    ruleLabel: 'C=3（法対応要整備：Q16 未整備/わからない OR Q17 未整備/一部のみ/わからない OR Q6=NO）',
    predicate: (s) => s.C === 3,
  },
  {
    priority: 2,
    patternId: 'C',
    ruleLabel: 'L=3 かつ A>=2 かつ Q15=YES（多拠点＋階層承認＋拡張計画）',
    predicate: (s) => s.L === 3 && s.A >= 2 && s.answers.Q15 === ANS.YES,
  },
  {
    priority: 3,
    patternId: 'D',
    ruleLabel: 'L=3 かつ (Q5=NO または Q8=YES)（多拠点・本社集約せず／拠点別ルール）',
    predicate: (s) => s.L === 3 && (s.answers.Q5 === ANS.NO || s.answers.Q8 === ANS.YES),
  },
  {
    priority: 4,
    patternId: 'B',
    ruleLabel: 'L=2 かつ A=2（少拠点＋2段階承認）',
    predicate: (s) => s.L === 2 && s.A === 2,
  },
  {
    priority: 5,
    patternId: 'A',
    ruleLabel: 'L=1 かつ A=1 かつ C=1（単一拠点＋1段階承認＋基本整備）',
    predicate: (s) => s.L === 1 && s.A === 1 && s.C === 1,
  },
  // priority 6 はコード内で nearestPattern により解決。ruleLabel は固定文言を付与。
];

const FALLBACK_RULE_LABEL = 'フォールバック（最近傍、確定度: 中）';
```

### 6.3 副次マッチ検出

決定表マッチ後、マッチ済みルールより**下位**の各ルールも `predicate` 評価を行い、true の場合は `subMatches` に `ruleLabel` を push する（要件§10.3.3 副次マッチ併記要件）。

### 6.4 起動時バリデーション（設計§5.2.2）

```js
function validateConfig() {
  const warns = [];
  // 基本チェック（CS-R1-3）
  for (const r of PATTERN_RULES) {
    if (!PATTERNS[r.patternId]) warns.push(`PATTERN_RULES[${r.priority}] の patternId='${r.patternId}' が PATTERNS に存在しない`);
    if (!r.ruleLabel) warns.push(`PATTERN_RULES[${r.priority}] の ruleLabel が未定義`);
    // mS-R3-2 ② predicate は関数必須
    if (typeof r.predicate !== 'function') warns.push(`PATTERN_RULES[${r.priority}] の predicate が関数ではない`);
  }
  // mS-R3-2 ① priority 重複／欠番検出（1..N の連番必須）
  const priorities = PATTERN_RULES.map(r => r.priority);
  const dup = priorities.filter((p,i) => priorities.indexOf(p) !== i);
  if (dup.length) warns.push(`PATTERN_RULES の priority 重複: ${[...new Set(dup)].join(',')}`);
  const sorted = [...priorities].sort((a,b) => a-b);
  for (let i = 0; i < sorted.length; i++) {
    if (sorted[i] !== i+1) { warns.push(`PATTERN_RULES の priority に欠番（連番 1..${sorted.length} 必須、実値: ${sorted.join(',')}）`); break; }
  }
  // mS-R3-2 ③ PATTERNS[pid].detail は配列で最低 1 要素以上
  for (const [pid, p] of Object.entries(PATTERNS)) {
    if (!Array.isArray(p.detail) || p.detail.length === 0) {
      warns.push(`PATTERNS['${pid}'].detail が配列かつ 1 要素以上である必要がある（§6.1 CS-R2-2）`);
    }
  }
  // mS-R3-2 ④ reasonHighlights の参照整合（buildReasonHighlights に出現する qids が QUESTIONS に存在）
  const REFERENCED_QIDS = ['Q2','Q4','Q3','Q5','Q7','Q6','Q12','Q13','Q16','Q17','Q15','Q1'];
  for (const qid of REFERENCED_QIDS) {
    if (!(qid in QUESTIONS)) warns.push(`判定系参照 qid='${qid}' が QUESTIONS に存在しない`);
  }
  if (warns.length) {
    console.warn('[config]', warns);
    Render.showConfigErrorBanner(warns);  // splash に「設定エラー」バナー表示
  }
  return warns.length === 0;                // ※ AppCore.init() は戻り値 false の場合に開始ボタンを disabled 化し return（CS-R1-3）
}
```

---

## 7. DOM 構造骨格

### 7.1 HTML 全体骨格

```html
<!doctype html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>運用整備ナビゲーター</title>
  <style>/* 全CSSインライン（画面用 + @media print） */</style>
</head>
<body>
  <!-- M-14 免責バー：全画面で常時表示（画面表示時のみ sticky、印刷時は §10.3 参照） -->
  <header id="app-header" role="banner">
    <p id="disclaimer" aria-live="polite">
      本ツールは診断補助であり、法令判定ではありません。最終判断は専門家レビューを前提とします。
    </p>
  </header>

  <main id="app-root">
    <!-- 画面切替は Render.show(screenId) が data-active 属性で制御 -->

    <section id="screen-splash" data-screen data-active="true" aria-labelledby="splash-title">
      <h1 id="splash-title">運用整備ナビゲーター</h1>
      <p>YES/NO 簡易診断（所要時間 約5分）</p>
      <div class="splash-modal" role="dialog" aria-labelledby="persist-title">
        <h2 id="persist-title">回答の保存</h2>
        <label><input type="radio" name="persist" value="none" checked> 保存しない（一時利用）</label>
        <label><input type="radio" name="persist" value="local"> 保存する（続きから再開可能）</label>
        <button id="btn-start-short" type="button">ショート版で開始（7問／約3分）</button>
        <button id="btn-start-full" type="button">フル版で開始（15問／約7分）</button>
        <!-- btn-resume: persist=local が選択されていて、かつ hasSavedSession() が true のときのみ表示・活性化（CS-R1-1／§11.1.1）。
             persist=none の状態では必ず hidden かつ無効。ラジオ切替でも都度再評価する。 -->
        <button id="btn-resume" type="button" hidden disabled>続きから再開</button>
      </div>
      <button id="btn-clear-storage" type="button">保存データをクリア</button>
    </section>

    <section id="screen-question" data-screen hidden aria-labelledby="q-title">
      <!-- aria-valuemax / progress-text の初期値 "7" はダミー。Render.renderQuestion() 呼び出し時に
           Flow.progress() の {done,total} で即座に上書きされる。フル版は分岐により total が可変となるため
           HTML 側の初期値を固定値として解釈しないこと（mS-R1-2）。 -->
      <div id="progress" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="7"
           title="到達予定数は回答により変動する場合があります">
        <span id="progress-text">0 / 7</span>
        <div id="progress-bar"><div id="progress-bar-fill"></div></div>
      </div>
      <h2 id="q-title"></h2>
      <details><summary>これはどういう意味？</summary><p id="q-hint"></p></details>
      <div id="q-choices" role="radiogroup" aria-labelledby="q-title"></div>
      <div class="q-nav">
        <button id="btn-back" type="button">← 戻る</button>
      </div>
    </section>

    <section id="screen-result" data-screen hidden aria-labelledby="r-title">
      <article id="pattern-card">
        <h2 id="r-title"></h2>
        <section aria-label="該当理由"><h3>該当理由</h3><ul id="r-reasons"></ul></section>
        <section aria-label="推奨設定"><h3>推奨設定サマリ</h3><ol id="r-summary5"></ol></section>
        <section aria-label="要ヒアリング項目">
          <h3>要ヒアリング</h3><ul id="r-hearing-tags" class="tag-yellow"></ul>
        </section>
        <section aria-label="設定工数目安"><h3>設定工数目安</h3><p id="r-effort"></p></section>
        <section aria-label="注意点・リスク"><h3>注意点 / リスク</h3><ul id="r-cautions"></ul></section>
        <!-- CS-R2-3: 企業名等（PII）の入力は「企業名等を入力する」トグル（既定 閉）を開いたときのみ表示。
             `pii` は §11.3 に従い `companyName` / `contactName` / `date` の 3 項目固定。未入力時は伏せ字／空欄。
             入力内容は localStorage に保存しない（§4.5 保存除外）。 -->
        <section aria-label="企業名等の入力">
          <button id="btn-toggle-pii" type="button" aria-expanded="false" aria-controls="pii-fields">
            企業名等を入力する
          </button>
          <div id="pii-fields" hidden>
            <label for="inp-company-name">企業名</label>
            <input id="inp-company-name" type="text" autocomplete="off" inputmode="text" placeholder="例: 株式会社クロスリンク" data-pii="companyName">
            <label for="inp-contact-name">担当者名</label>
            <input id="inp-contact-name" type="text" autocomplete="off" inputmode="text" placeholder="例: 中野 雅樹" data-pii="contactName">
            <label for="inp-date">日付</label>
            <input id="inp-date" type="date" data-pii="date">
            <p class="pii-note no-print">入力欄は編集フォーカス時以外マスキング表示（例: 株式会社●●●）。入力値は localStorage に保存されません。</p>
          </div>
        </section>
        <section aria-label="営業担当者向けメモ">
          <label for="sales-memo">営業担当者向けメモ（任意）</label>
          <textarea id="sales-memo" rows="3" placeholder="（詳細版印刷時のみ・『営業メモを印字する』トグル ON のときだけ印字）"></textarea>
        </section>
        <p class="elapsed">所要時間: <span id="r-elapsed">–</span></p>
      </article>
      <div class="result-actions">
        <button id="btn-print-summary" type="button">要約版を印刷</button>
        <button id="btn-print-detail" type="button">詳細版を印刷</button>
        <button id="btn-copy-summary" type="button">結果サマリをコピー</button>
        <button id="btn-restart" type="button">最初からやり直す</button>
        <button id="btn-clear-storage-2" type="button">保存データをクリア</button>
      </div>
    </section>

    <section id="screen-print" data-screen hidden aria-labelledby="print-title">
      <div class="print-controls no-print">
        <h2 id="print-title">印刷プレビュー</h2>
        <label><input type="radio" name="printMode" value="summary" checked> 要約版</label>
        <label><input type="radio" name="printMode" value="detail"> 詳細版</label>
        <label><input type="checkbox" id="chk-anonymize" checked> 匿名化して印刷</label>
        <label><input type="checkbox" id="chk-print-salesmemo"> 営業メモを印字する（詳細版のみ）</label>
        <button id="btn-do-print" type="button">印刷</button>
        <button id="btn-back-to-result" type="button">結果画面に戻る</button>
      </div>
      <div id="print-area">
        <!-- 印刷専用の免責ヘッダー（CS-R3-1）：CSS `@media print` で `position: fixed` により全ページ反復表示される（§10.4/§10.5）。sticky は不採用（印刷で初頁しか出ないため）。 -->
        <div class="disclaimer-print">本ツールは診断補助であり、法令判定ではありません。</div>
        <!-- CS-R2-3: 印刷ヘッダー領域の PII は `ui.anonymize` で伏せ字／平文を切替。
             Render.toPrint() が `#print-header-company` / `#print-header-contact` / `#print-header-date` に差し込む。
             匿名化 ON の初期表示（例: 株式会社●●●・●● ●●）は CSS 変数で差し替えるのではなく Render が生成済み文字列を書き込む。 -->
        <div id="print-header" class="print-header">
          <span id="print-header-company" data-pii="companyName"></span>
          <span id="print-header-contact" data-pii="contactName"></span>
          <span id="print-header-date" data-pii="date"></span>
        </div>
        <div id="print-body"><!-- Render.toPrint() が差し込み --></div>
      </div>
    </section>
  </main>

  <script>/* 全JS インライン（§8 参照） */</script>
</body>
</html>
```

### 7.2 主要 CSS クラス設計

| クラス/ID | 用途 |
|-----------|------|
| `#app-header` | M-14 固定免責バー。画面表示時 `position: sticky; top:0;` |
| `[data-screen]` / `[data-active="true"]` | 画面切替。他は `hidden` 属性。 |
| `.tag-yellow` | 要ヒアリングバッジ（黄色、§9.1 エラー処理でも黄色統一） |
| `.disclaimer-print` | 印刷専用免責（sticky ではなく `@media print` 下で `position: fixed` により全ページ反復。CS-R3-1／§10.4） |
| `.no-print` | `@media print { .no-print { display: none; } }` |
| `.print-summary` / `.print-detail` | 印刷モード切替用の body クラス |

### 7.3 ARIA 属性方針（最小限）

- `role="banner"` (app-header), `role="radiogroup"` (選択肢群), `role="progressbar"`, `role="dialog"`
- `aria-live="polite"` は免責バー（変わらない前提だが、後日動的更新に対応するため）
- 選択肢ボタンは `<button>` 要素でキーボードフォーカス可。Y/N ショートカットは `keydown` で補助。
- `aria-valuenow/min/max` を進捗バーで更新（Flow.progress() に連動して都度再計算。HTML 上の `aria-valuemax="7"` は初期ダミーで、`Render.updateProgress()` が即座に上書きする）。

---

## 8. JS モジュール仕様（IIFE + 名前空間）

設計§2.2 / §3 に従い、単一 `<script>` 内で 6 モジュールに分割する。

```js
(function(){
  'use strict';
  const ANS = { /* §4.1 */ };
  const QUESTIONS = { /* §5.1 */ };
  const SHORT_ROUTE = [ /* §5.2 */ ];
  const PATTERNS = { /* §6.1 */ };
  const PATTERN_RULES = [ /* §6.2 */ ];
  const DEBUG = false;

  const State = (function(){ /* §8.1 */ })();
  const Persist = (function(){ /* §8.2 */ })();
  const Flow = (function(){ /* §8.3 */ })();
  const Judge = (function(){ /* §8.4 */ })();
  const Render = (function(){ /* §8.5 */ })();
  const AppCore = (function(){ /* §8.6 */ })();

  document.addEventListener('DOMContentLoaded', () => AppCore.init());
})();
```

### 8.1 State

```js
const State = (function(){
  let current = defaultState();
  function defaultState(){ return { /* §4.3 のスキーマ */ }; }

  return {
    get: () => current,
    setAnswer: (qid, val) => { current.answers[qid] = val; },
    setMode: (m) => { current.mode = m; },
    setScreen: (s) => { current.screen = s; },
    setCurrentQid: (qid) => { current.currentQid = qid; },
    pushHistory: (qid) => { current.history.push(qid); },
    popHistory: () => current.history.pop(),
    reset: () => { current = defaultState(); },
    snapshot: () => JSON.parse(JSON.stringify(current)),
    // applySnapshot は浅いマージ。`ui` / `pii` / `salesMemo` / `startedAt` / `completedAt` / `result` は
    // 保存ペイロード側で除外済み（§4.5）なので snap に含まれない前提。将来キーが増えても current の既定値
    // が維持されるよう、保存対象キーの追加は §4.5 と §8.2 `Persist.save` の payload を必ず同時更新すること（mS-R1-5）。
    // 必須最小キー: { mode, persistMode, currentQid, shortIndex, answers, history, appVersion }
    applySnapshot: (snap) => { Object.assign(current, snap); },
  };
})();
```

### 8.2 Persist

```js
/**
 * @typedef {Object} PersistPayload
 * @property {string} appVersion     - 現行は '1.0.0'（v1系）固定。非互換時は破棄
 * @property {'full'|'short'} mode
 * @property {'local'} persistMode   - 保存されている時点で必ず 'local'（復元後の save 再開を保証）
 * @property {string} currentQid
 * @property {number} shortIndex
 * @property {Object} answers
 * @property {string[]} history
 */
const Persist = (function(){
  const KEY = 'cs_yesno_diag_v1';
  const SUPPORTED_MAJOR = '1';                                       // appVersion の先頭セグメント（mS-R1-3）

  function isAvailable(){
    try { const k='__t'; localStorage.setItem(k,'1'); localStorage.removeItem(k); return true; }
    catch(e){ return false; }
  }
  function hasSavedSession(){
    try { return !!localStorage.getItem(KEY); } catch(e){ return false; }
  }
  function save(){
    if (State.get().persistMode !== 'local') return;                // §11.1 絶対ガード
    const s = State.get();
    // CS-R2-1: 空セッション（splash / currentQid=null）を保存しない。
    //   `none→local` トグル直後はまだ mode='splash' のため、ここで弾く。
    //   `PersistPayload.mode` は 'full'|'short' のみを取り得る（スキーマ不整合の予防）。
    if (s.mode !== 'full' && s.mode !== 'short') return;
    if (!s.currentQid) return;
    /** @type {PersistPayload} */
    const payload = {
      appVersion: s.appVersion, mode: s.mode, persistMode: 'local',  // CS-R1-2: persistMode を保存して復元後の save 再開を保証
      currentQid: s.currentQid, shortIndex: s.shortIndex,
      answers: s.answers, history: s.history,
      // pii / salesMemo / ui / startedAt / completedAt / result は保存しない（§4.5, §11.3）
    };
    try { localStorage.setItem(KEY, JSON.stringify(payload)); }
    catch(e){ State.get().ui.localStorageWarning = true; }
  }
  function isValidPayload(snap){
    // MS-R2-4: ペイロードの必須キー／型チェック。破損 JSON で画面遷移が壊れるのを防ぐ。
    if (!snap || typeof snap !== 'object') return false;
    if (typeof snap.appVersion !== 'string') return false;
    if (snap.mode !== 'full' && snap.mode !== 'short') return false;
    if (snap.persistMode !== 'local') return false;
    if (typeof snap.currentQid !== 'string' || !snap.currentQid) return false;
    if (typeof snap.shortIndex !== 'number') return false;
    if (!snap.answers || typeof snap.answers !== 'object') return false;
    if (!Array.isArray(snap.history)) return false;
    // MS-R3-1: 整合チェック強化。型だけ合っていて中身が壊れているデータで復元が破綻するのを防ぐ。
    //   ① currentQid が QUESTIONS に存在する
    if (!(snap.currentQid in QUESTIONS)) return false;
    //   ② history の各要素が string かつ QUESTIONS に存在する
    for (const qid of snap.history) {
      if (typeof qid !== 'string' || !(qid in QUESTIONS)) return false;
    }
    //   ③ shortIndex 範囲（short: 0..SHORT_ROUTE.length-1 / full: 常に 0）
    if (snap.mode === 'short') {
      if (!Number.isInteger(snap.shortIndex)) return false;
      if (snap.shortIndex < 0 || snap.shortIndex >= SHORT_ROUTE.length) return false;
      //   ④ short モード時は currentQid が SHORT_ROUTE[shortIndex] と一致する
      if (snap.currentQid !== SHORT_ROUTE[snap.shortIndex]) return false;
    } else {
      // full モードでは shortIndex は 0 固定（Flow.startFull が 0 にリセットするため）
      if (snap.shortIndex !== 0) return false;
    }
    return true;
  }
  function load(){
    // §11.1.1: 起動時自動呼出し禁止。明示 (C) ルートからのみ呼ぶ
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return false;
      let snap;
      try { snap = JSON.parse(raw); }
      catch(e){ clear(); return false; }                            // MS-R2-4: 破損 JSON は破棄して false
      // appVersion 非互換時は破棄（移行処理なし、mS-R1-3）
      const major = typeof snap.appVersion === 'string' ? snap.appVersion.split('.')[0] : '';
      if (major !== SUPPORTED_MAJOR) { clear(); return false; }
      // MS-R2-4: スキーマ検証失敗時も破棄
      if (!isValidPayload(snap)) { clear(); return false; }
      State.applySnapshot(snap);
      return true;
    } catch(e){ clear(); return false; }
  }
  function clear(){
    try { localStorage.removeItem(KEY); } catch(e){}
  }
  return { isAvailable, hasSavedSession, save, load, clear };
})();
```

### 8.3 Flow

```js
/**
 * @typedef {{done:number, total:number}} FlowProgress
 * @typedef {{nextQid?:string, done?:true, noop?:true, prevQid?:string}} FlowStepResult
 */
const Flow = (function(){
  function startFull(){
    State.setMode('full'); State.setCurrentQid('Q1');
    State.get().history = []; State.get().shortIndex = 0;
    State.get().startedAt = Date.now();
  }
  function startShort(){
    State.setMode('short'); State.setCurrentQid(SHORT_ROUTE[0]);
    State.get().history = []; State.get().shortIndex = 0;
    State.get().startedAt = Date.now();
  }
  function next(){
    const s = State.get();
    let nextQid;
    if (s.mode === 'short') {
      if (s.shortIndex + 1 >= SHORT_ROUTE.length) return { done: true };
      State.pushHistory(s.currentQid);
      s.shortIndex += 1;
      nextQid = SHORT_ROUTE[s.shortIndex];
      State.setCurrentQid(nextQid);
      return { nextQid };
    }
    nextQid = QUESTIONS[s.currentQid].branch(s);
    if (nextQid === null) return { done: true };
    State.pushHistory(s.currentQid);
    State.setCurrentQid(nextQid);
    return { nextQid };
  }
  function back(){
    const s = State.get();
    if (s.history.length === 0) return { noop: true };
    const prev = State.popHistory();
    delete s.answers[s.currentQid];                // 未回答に戻す
    if (s.mode === 'short') s.shortIndex = Math.max(0, s.shortIndex - 1);
    State.setCurrentQid(prev);
    return { prevQid: prev };
  }
  function canGoBack(){ return State.get().history.length > 0; }
  function current(){ return State.get().currentQid; }

  function estimateRemaining(){
    // 設計§7.1.1 実装規約
    const s = State.get();
    if (s.mode === 'short') return SHORT_ROUTE.length - s.shortIndex - 1;
    const seen = new Set();
    let qid = QUESTIONS[s.currentQid].branch(s);
    let count = 0;
    const MAX = Object.keys(QUESTIONS).length;
    while (qid && count < MAX) {
      if (seen.has(qid)) break;
      seen.add(qid);
      count++;
      qid = QUESTIONS[qid].branch(s);
    }
    return count;
  }
  function progress(){
    const s = State.get();
    if (s.mode === 'short') {
      return { done: s.shortIndex, total: SHORT_ROUTE.length };
    }
    return {
      done: s.history.length,
      total: s.history.length + 1 + estimateRemaining(),
    };
  }
  return { startFull, startShort, next, back, canGoBack, current, progress, estimateRemaining };
})();
```

### 8.4 Judge

```js
const Judge = (function(){
  function calcL(a){
    if (a.Q2 === ANS.YES) return 3;
    if (a.Q2 === ANS.NO && a.Q4 === ANS.YES) return 2;
    return 1;
  }
  function calcAFull(a, L){
    let A = 1;
    if (a.Q3 === ANS.YES) A = Math.max(A, 2);
    if (a.Q5 === ANS.YES && L >= 2) A = Math.max(A, 2);
    if (a.Q7 === ANS.YES) A = 1;
    return A;
  }
  function calcAShort(a){
    // Q7 未回答時: Q3=YES → 2, それ以外 → 1
    return a.Q3 === ANS.YES ? 2 : 1;
  }
  function calcCFull(a){
    // MS-R2-1: 要件§10.3.2 を正として PATTERN_RULES の E ruleLabel と整合。
    //   C=2: Q12=YES（抵触日対象案件あり）
    //   C=3: Q16 未整備/わからない OR Q17 未整備/一部のみ/わからない OR Q6=NO
    //   （Q17=PART は要件書で E 条件に含まれるため C=3 に昇格する）
    let C = 1;
    if (a.Q12 === ANS.YES) C = Math.max(C, 2);
    if (a.Q16 === ANS.NOT_READY || a.Q16 === ANS.UNKNOWN
        || a.Q17 === ANS.PART
        || a.Q17 === ANS.NOT_READY || a.Q17 === ANS.UNKNOWN
        || a.Q6 === ANS.NO) {
      C = 3;
    }
    return C;
  }
  function calcCShort(a){
    let C = 1;
    if (a.Q12 === ANS.YES || a.Q12 === ANS.UNKNOWN) C = Math.max(C, 2);
    // Q16/Q17 は未回答のためショート版では C=3 発火しない
    return C;
  }
  function calcFlags(a){ return { proxyApprovalMissing: a.Q6 === ANS.NO }; }
  // mS-R3-1: P 軸はフル版のみ Q1 で評価する。**ショート版は `SHORT_ROUTE` に Q1 を含まないため P 軸未評価**だが、
  //   実装上は `a.Q1===undefined` → `=== ANS.YES` が false となり **COARSE 扱いで確定**する（未評価を別値で持たない）。
  //   これは「ショート版は P 軸を COARSE と仮置きする」という仕様上の明示的な振る舞い（§5.2 参照）。
  //   P 軸を真に評価したい場合はフル版を使うこと。
  function calcP(a){ return a.Q1 === ANS.YES ? 'FINE' : 'COARSE'; }

  function collectTags(a, mode, fallback){
    const tags = [];
    for (const q of Object.values(QUESTIONS)) {
      const ans = a[q.id];
      if (ans === undefined) continue;
      const t = q.triage(ans);
      if (t.needHearing) tags.push(`要ヒアリング: ${t.reason}`);
    }
    if (mode === 'short') {
      tags.push('要ヒアリング（省略項目あり）: Q1/Q4/Q7/Q8/Q9/Q10/Q14/Q16/Q17');
    }
    if (fallback) tags.push('要ヒアリング（確定度: 中）');
    return tags;
  }

  function nearestPattern(scores){
    // L/A/C の距離最小でフォールバック。各パターン代表スコアと比較。
    const refs = {
      A:{L:1,A:1,C:1}, B:{L:2,A:2,C:2}, C:{L:3,A:2,C:2}, D:{L:3,A:2,C:1}, E:{L:2,A:2,C:3},
    };
    let best='A', bestDist=Infinity;
    for (const [id,r] of Object.entries(refs)) {
      const d = Math.abs(r.L-scores.L) + Math.abs(r.A-scores.A) + Math.abs(r.C-scores.C);
      if (d < bestDist) { bestDist = d; best = id; }
    }
    return best;
  }

  function buildReasonHighlights(scores, answers, pattern){
    // mS-R1-4: axis は 'L'|'A'|'C'|'EXT' の4値（scores には含まれない 'EXT' は拡張計画専用の表示フィールド）
    const hl = [];
    hl.push({ axis:'L', value: scores.L, qids:['Q2','Q4'] });
    hl.push({ axis:'A', value: scores.A, qids:['Q3','Q5','Q7'] });
    hl.push({ axis:'C', value: scores.C, qids:['Q6','Q12','Q13','Q16','Q17'] });
    if (answers.Q15 === ANS.YES) hl.push({ axis:'EXT', value:'YES', qids:['Q15'] });
    return hl;
  }

  function evaluate(){
    const s = State.get();
    const a = s.answers;
    const L = calcL(a);
    const A = s.mode === 'short' ? calcAShort(a) : calcAFull(a, L);
    const C = s.mode === 'short' ? calcCShort(a) : calcCFull(a);
    const P = calcP(a);
    const flags = calcFlags(a);
    const scoreCtx = { L, A, C, P, flags, answers: a };

    let matched = null;
    const subMatches = [];
    for (const rule of PATTERN_RULES) {
      if (rule.predicate(scoreCtx)) {
        if (!matched) matched = rule;
        else subMatches.push(rule.ruleLabel);
      }
    }
    let pattern, priorityMatched, fallback = false;
    if (matched) {
      pattern = matched.patternId;
      priorityMatched = matched.priority;
    } else {
      pattern = nearestPattern({L,A,C});
      priorityMatched = 6;
      fallback = true;
    }
    const tags = collectTags(a, s.mode, fallback);
    return {
      patternId: pattern, priorityMatched,
      scores: { L, A, C, P }, flags,
      tags, subMatches,
      reasonHighlights: buildReasonHighlights({L,A,C}, a, pattern),
      fallback,
    };
  }
  return { evaluate };
})();
```

### 8.5 Render

公開関数:
```js
Render.show(screenId)              // 画面切替
Render.renderQuestion()            // 現在質問を描画、進捗更新
Render.renderResult()              // State.result から pattern-card を組立
Render.toPrint(mode)               // 'summary'|'detail'：print-body を構築。入力は State.result（JudgeResult）と State.ui、
                                   // mode==='detail' の場合のみ §10.3 PrintDetailModel を生成して出力。要約版では
                                   // PrintDetailModel.answers / checkList / matchedRule / salesMemo は一切生成しない（MS-R1-3）
Render.showLocalStorageWarning()   // 黄バナー表示
Render.showConfigErrorBanner(msgs) // バリデーション失敗時
Render.disableStartButtons()       // CS-R1-3: validateConfig 失敗時に btn-start-short/full/resume を全て disabled にする
Render.updateResumeButton(show)    // CS-R1-1 / MS-R3-2: boolean 引数のみ受け取り、`btn-resume` の hidden/disabled を更新する。
                                   // Persist/Flow/Judge を直接呼ばない（設計§3.2 の Render 責務境界を厳守）。
                                   // 判定ロジック（isAvailable / hasSavedSession / persist ラジオ値の論理積）は AppCore 側に置く。
Render.updateBackButton(enabled)   // 戻るボタン活性制御
Render.updateProgress({done,total})
Render.togglePiiFields(open)       // CS-R2-3: #pii-fields の表示/非表示と aria-expanded を同期（State.ui.piiFieldsOpen と連動）
Render.maskPiiField(inputEl)       // CS-R2-3: 編集フォーカス時以外のマスキング表示切替（focus/blur ハンドラから呼ぶ）
```

Render は State を**読むのみ**。Flow/Judge/Persist を直接呼ばない（設計§3.2）。

### 8.6 AppCore

オーケストレータ。イベントバインドと戻り値の捌き。

```js
const AppCore = (function(){
  function init(){
    bindEvents();
    // CS-R1-3: 設定エラー時は開始ボタンを無効化して起動中断（以降の Render.show('splash') は行うが操作不可）
    if (!validateConfig()) {
      Render.disableStartButtons();
      Render.show('splash');
      return;
    }
    if (!Persist.isAvailable()) {
      State.get().ui.localStorageWarning = true;
      Render.showLocalStorageWarning();
    }
    // CS-R1-1 / MS-R3-2: btn-resume の表示判定は AppCore 側で行い、Render には boolean を渡すだけに限定。
    //   - 初期状態は persist=none のため show=false（必ず hidden/disabled）。
    //   - ラジオ change イベントでも computeResumeVisibility→updateResumeButton を呼び、切替に追従する（bindEvents 側で登録）。
    Render.updateResumeButton(computeResumeVisibility());
    Render.show('splash');
  }
  function computeResumeVisibility(){
    // MS-R3-2: Render から分離した判定ロジック。3 条件の論理積で boolean を返す（§11.1.1）。
    const persistRadio = document.querySelector('input[name="persist"]:checked');
    const persistVal = persistRadio ? persistRadio.value : 'none';
    return Persist.isAvailable() && Persist.hasSavedSession() && persistVal === 'local';
  }
  function onPersistChange(){
    // persist ラジオ切替時のハンドラ（bindEvents から登録）
    const persistRadio = document.querySelector('input[name="persist"]:checked').value;
    const prev = State.get().persistMode;
    State.get().persistMode = persistRadio;
    // §11.1 モードトグル時の即時保存（prev と新値の差分で即時 save / clear）
    if (prev === 'none' && persistRadio === 'local') Persist.save();
    if (prev === 'local' && persistRadio === 'none') Persist.clear();
    Render.updateResumeButton(computeResumeVisibility());            // CS-R1-1 / MS-R3-2: ラジオ変更に追従（判定は AppCore 側）
  }
  function onStart(mode){
    // ラジオ切替は onPersistChange 側で state 反映済み想定。ここでは念のため再同期のみ。
    const persistRadio = document.querySelector('input[name="persist"]:checked').value;
    if (State.get().persistMode !== persistRadio) onPersistChange();

    if (mode === 'short') Flow.startShort(); else Flow.startFull();
    State.setScreen('question');
    Render.show('question');
    Render.renderQuestion();
    Persist.save();
  }
  function onResume(){
    // CS-R1-1: 2 アクション明示ガード。persist=local が選択されていない状態では load() を呼ばない。
    const persistRadio = document.querySelector('input[name="persist"]:checked').value;
    if (persistRadio !== 'local') return;
    if (!Persist.load()) return;
    // CS-R1-2: 復元ペイロードは persistMode='local' を含むが、念のため明示セットして save 再開を保証する。
    State.get().persistMode = 'local';
    State.setScreen('question');
    Render.show('question');
    Render.renderQuestion();
  }
  function onAnswer(qid, val){
    State.setAnswer(qid, val);
    const r = Flow.next();
    Persist.save();
    if (r.done) {
      State.get().completedAt = Date.now();
      State.get().result = Judge.evaluate();
      State.setScreen('result');
      Render.show('result');
      Render.renderResult();
    } else {
      Render.renderQuestion();
    }
  }
  function onBack(){
    const r = Flow.back();
    if (r.noop) return;
    Persist.save();
    Render.renderQuestion();
  }
  function onRestart(){
    State.reset();
    Persist.clear();
    Render.show('splash');
  }
  function onClearStorage(){
    Persist.clear();
    State.reset();
    Render.show('splash');
  }
  function onPrint(mode){
    State.get().ui.printMode = mode;
    State.setScreen('print');
    Render.show('print');
    Render.toPrint(mode);
  }
  function onDoPrint(){
    try { window.print(); }
    catch(e){ /* 印刷不可は §9 でフォールバック */ }
  }
  function onCopySummary(){ /* §10.1.1 */ }
  function bindEvents(){ /* 上記ハンドラを DOM にバインド */ }

  return { init, onStart, onResume, onPersistChange, onAnswer, onBack, onRestart, onClearStorage, onPrint, onDoPrint, onCopySummary };
})();
```

---

## 9. エラー処理と異常系

> **終了コードについて（MS-R1-4）**: 本プロジェクトはブラウザ実行の単一 HTML アプリであり、プロセス終了コードの概念は存在しない（**N/A**）。異常時は画面内バナー／ボタン無効化／トーストで扱い、`process.exit` / `throw` 伝播による UA 終了は行わない。

**N/A 観点一覧（mS-R3-3）**: 汎用レビュー観点 E（エッジケース）のうち本案件に該当しない項目を以下に整理して論点を閉じる。

| 観点 | 扱い | 理由 |
|------|------|------|
| 日時境界（24:00 / うるう秒 / TZ） | **N/A** | 入力は `<input type="date">` のみ。時刻・TZ を扱わない |
| 文字コード混在（CP932/UTF-8） | **N/A** | 単一 HTML で `<meta charset="UTF-8">` 固定。ファイル I/O なし |
| プロセス終了コード | **N/A** | ブラウザ実行のため（MS-R1-4 既出） |
| i18n / 多言語化 | **N/A** | 日本語単一。要件書に多言語要件なし |
| 並行処理・レースコンディション | **N/A** | 単一タブ・シングルスレッド（Web Worker 不使用）。localStorage 書込みも同期 |
| ネットワーク障害 | **N/A** | `file://` 前提・外部通信禁止（§11.5 / §11.6） |

### 9.1 エラー分類と挙動

| 区分 | 条件 | 挙動 |
|------|------|------|
| 致命 | `QUESTIONS` または `PATTERN_RULES` 不整合（`validateConfig` 失敗） | splash に「設定エラー」バナー、`btn-start-short`/`btn-start-full`/`btn-resume` を disabled、`AppCore.init` は `return` して以降の初期化を中断（CS-R1-3） |
| 警告 | localStorage 不可 | 画面上部黄バナー「保存機能は無効です。セッション中のみ回答保持」 |
| 警告 | clipboard 不可 | サマリコピー時、テキスト選択済みモーダル表示（手動コピー） |
| 警告 | `window.print()` 失敗 | print 画面は表示し「ブラウザの印刷機能（Ctrl/Cmd+P）をお使いください」注記を追加表示 |
| 情報 | 戻る/やり直し/保存クリア | 画面内トースト（2秒） |

### 9.2 フォールバック判定（決定表どれもマッチせず）
- `Judge.evaluate` が `fallback:true` を返し、結果カードに**黄色**の「要ヒアリング（確定度: 中）」バッジを付与（要ヒアリングは重大度問わず黄色統一、設計§10.2）。
- `patternId` は `nearestPattern` で算出（§8.4）。

### 9.3 ログ
- 本番: `console.*` 出力なし。ただし **起動時バリデーション `validateConfig()` が構成不整合を検出した場合のみ `console.warn('[config]', warns)` を出力する**（§6.4、開発者が異常を検出可能にするため。mS-R2-2）。
- `DEBUG=true` 時のみ Flow/Judge の遷移を `console.debug`。

---

## 10. 印刷 CSS 仕様

### 10.1 基本方針
- 印刷モード切替は `<body class="print-summary">` / `<body class="print-detail">` の切替で実現（設計付録C）。
- 用紙: A4 縦、余白 10mm。モノクロ印刷判読可能。

### 10.2 要約版（A4 縦 1 枚）
- ヘッダー（企業名・日付・匿名化時は伏せ字）
- パターン名（色分け）
- 該当理由（3行程度）
- 推奨設定サマリ（`summary5` の5項目）
- 免責文（`.disclaimer-print`）
- **営業メモは非印字**（§11.3）

### 10.3 詳細版（A4 縦 2〜3 枚）
- 要約版の全要素 ＋
- 回答一覧（`answers[]`、下記 `PrintDetailModel`）
- 設定項目チェックリスト（`checkList[]`）
- マッチルール：`matchedRule.predicateText`（= `PATTERN_RULES` の `ruleLabel`。関数を文字列化しない）
- 要ヒアリングタグ一覧
- 営業メモ（**`State.ui.printSalesMemo === true` のときのみ印字**。匿名化トグル OFF 単独では印字しない。CS-R1-4 による真理値表固定 → §11.3 表参照）

#### PrintDetailModel 型定義（MS-R1-3）

詳細版印刷の入出力契約を固定するための typedef。`Render.toPrint('detail')` はこの型を組み立てて `#print-body` にレンダリングする。summary 版ではこの型を生成せず、`header` と `patternId` / `summary5` / `cautions` / `effort` / 免責のみ出力する。

```js
/**
 * @typedef {Object} PrintDetailModel
 * @property {PrintHeader} header                - 企業名/担当者名/日付（匿名化ON時は伏せ字）
 * @property {string} patternId                  - 'A'|'B'|'C'|'D'|'E'
 * @property {string} patternName                - 例「複数拠点対応型」
 * @property {PrintAnswer[]} answers             - 回答一覧（質問ID/質問文/回答ラベル/軸寄与の4列）
 * @property {PrintMatchedRule} matchedRule      - priority, ruleLabel, fallback フラグ
 * @property {PrintChecklistItem[]} checkList    - 設定項目チェックリスト（PATTERNS.detail から展開）
 * @property {string[]} hearingTags              - 要ヒアリングタグ（State.result.tags）
 * @property {PrintSalesMemoBlock|null} salesMemo - State.ui.printSalesMemo===true のときだけ値あり、それ以外は null
 *
 * @typedef {Object} PrintHeader
 * @property {string} companyName                - 匿名化ON時は '株式会社●●●' 等の伏せ字
 * @property {string} contactName                - 同上（CS-R1-5 で PII に追加）
 * @property {string} date
 *
 * @typedef {Object} PrintAnswer
 * @property {string} qid
 * @property {string} text
 * @property {string} answerLabel                - 表示用ラベル（内部コードではなく日本語）
 * @property {string} answerCode                 - 内部コード（ANS.* の値、設計§5.2 `answers[].answerCode` を反映、MS-R2-2）
 * @property {string[]} axis                     - ['L','A','C','P'] の部分集合
 *
 * @typedef {Object} PrintMatchedRule
 * @property {1|2|3|4|5|6} priority
 * @property {string} predicateText              - = PATTERN_RULES[i].ruleLabel（関数文字列化禁止）
 * @property {boolean} fallback
 *
 * @typedef {Object} PrintChecklistItem
 * @property {string} category
 * @property {string} label
 * @property {'推奨'|'要確認'|'要ヒアリング'} status  - 設計§5.2 `checkList[].status` を反映（MS-R2-2）。PATTERNS.detail[].status から展開
 *
 * @typedef {Object} PrintSalesMemoBlock
 * @property {string} text                       - 匿名化ON時は伏せ字処理済み、OFF時は平文
 */
```

### 10.4 印刷用 CSS スケルトン

```css
@media print {
  @page { size: A4 portrait; margin: 10mm; }
  /* CS-R3-1: `.disclaimer-print` を全ページ反復表示するため、body 上部に固定領域分の余白を確保する。
     `@page margin 10mm` + `body margin-top 14mm` で初頁の免責バーが本文と重ならないようにし、
     2 ページ目以降は `position: fixed` により印刷エンジンが各ページ先頭に複製する（Chromium/WebKit/Gecko 共通挙動）。 */
  body { font-family: "Hiragino Sans","Yu Gothic",sans-serif; font-size: 10.5pt; color: #000; margin-top: 14mm; }
  #app-header { position: static; }                 /* §11.4 sticky を外す（画面用スタイルを無効化） */
  .no-print { display: none !important; }
  /* CS-R3-1: 全ページ反復表示の実装契約。`position: fixed` + `top:0` により印刷エンジンが各ページ先頭へ複製する。
     `thead` 的な代替実装（`.disclaimer-print` を `display: table-header-group` にするなど）は行わない（ブラウザ差異が大きいため）。 */
  .disclaimer-print {
    display: block;
    position: fixed;
    top: 0; left: 0; right: 0;
    border-bottom: 1px solid #000;
    padding: 2mm 10mm;
    background: #fff;
    z-index: 9999;
  }
  #pattern-card { page-break-inside: avoid; }
  .section { page-break-inside: avoid; }
  .sales-memo-print { page-break-before: always; }  /* 詳細版で最終ブロック */
}

/* 画面時のみ */
@media screen {
  #app-header { position: sticky; top: 0; z-index: 100; background: #fffbe6; }
  .disclaimer-print { display: none; }               /* 画面時は #app-header 側で常時表示 */
}

body.print-summary .print-detail-only { display: none; }
body.print-detail  .print-summary-only { display: none; }
```

### 10.5 sticky 不使用の理由と全ページ反復方式の採用（設計§9.4, CS-R3-1）
- `position: sticky` は印刷時に初頁のみ出現／重なり切れ問題があるため不採用。
- 代替として `.disclaimer-print` に `position: fixed; top: 0;` を適用し、`@page margin 10mm` + `body margin-top 14mm` で本文と重ならない余白を確保した上で、**全ページの先頭に免責文を反復表示する実装契約に固定する**（CS-R3-1）。
- この方式は Chromium / WebKit / Gecko いずれも `@media print` 下の `position: fixed` を「各ページの該当位置に複製描画」する挙動を共有しており、単一 HTML 実装で追加 JS を使わずに全ページ反復を達成できる。
- テスト T-UI-18（§13.2）で「2 ページ以上になる詳細版印刷でも各ページに免責が出る」ことを実機確認する。

---

## 11. プライバシー・セキュリティ仕様

### 11.1 保存モード制御（M-11）

- splash モーダルの初期フォーカス＆初期チェック: `persistMode='none'`。
- モードトグル時の即時保存規約（設計§9.1 / CS-R2-1 反映）:
  - `none → local`: 切替直後に `Persist.save()` を呼ぶが、`save()` 側のガード（`mode ∈ {full,short} && currentQid`）により splash 段階では no-op になる。**最初に実ペイロードが書き込まれるのは質問開始時**（`onStart` / `onAnswer` の `Persist.save()`）。これにより `mode='splash' / currentQid=null` の空セッションは保存されない。
  - `local → none`: `Persist.clear()` を呼ぶ。
- `Persist.save()` 冒頭で `if (persistMode!=='local') return;` 絶対ガードに加え、**空セッション防止ガード**（`mode in {full,short} && currentQid` 必須）を設ける（CS-R2-1）。
- **復元後は `persistMode='local'` を保証**（CS-R1-2）。保存ペイロードに `persistMode` を含め、`Persist.load()` 成功後に `AppCore.onResume` が `State.get().persistMode='local'` を明示セットすることで、以降の `Persist.save()` が no-op 化するバグを防ぐ。
- **`Persist.load()` のペイロード妥当性検証**（MS-R2-4 / MS-R3-1）: 必須キー（`appVersion`/`mode`/`persistMode`/`currentQid`/`shortIndex`/`answers`/`history`）と型を検証し、失敗時は `clear()+false` を返して splash に留まる。破損 JSON でも画面遷移が壊れない。さらに MS-R3-1 として①`currentQid in QUESTIONS`、②`history` 各要素が string かつ `QUESTIONS` に存在、③`shortIndex` 範囲（short: 0..`SHORT_ROUTE.length-1` / full: 0 固定）、④`mode==='short'` 時 `currentQid===SHORT_ROUTE[shortIndex]` の整合チェックを追加。型だけ合った壊れたデータによる復元破綻を防ぐ。

### 11.1.1 `Persist.load()` 実行条件（設計§9.1.1 / CS-R1-1）
- **起動時に load() を呼ばない**。
- 復元が走るのは splash で「保存する」+「続きから再開」の 2 アクション明示時のみ。
- `hasSavedSession()` はキー存在チェックのみで内容を読まない。
- `btn-resume` の表示・活性化条件（UI 側での 2 アクション強制）:
  1. `Persist.isAvailable()` が true
  2. `Persist.hasSavedSession()` が true
  3. splash ラジオで `persist=local` が選択されている
  - **MS-R3-2: 責務分離**。3 条件の論理積は `AppCore.computeResumeVisibility()` が評価して boolean を返し、`Render.updateResumeButton(show)` はその boolean を受けて `hidden`／`disabled` 属性を更新するのみ。Render から Persist/Flow/Judge を直接呼ばない（設計§3.2）。`persist` ラジオの `change` イベントで `Render.updateResumeButton(computeResumeVisibility())` を再呼出し。
- `AppCore.onResume()` 冒頭では念のため `persist=local` 選択を再確認し、false の場合は `load()` を呼ばず no-op で終了する（ガード二重化）。

### 11.2 保存クリア（M-12）
- splash と result 画面に「保存データをクリア」ボタンを常設。
- 処理: `Persist.clear()` → `State.reset()` → `Render.show('splash')`。

### 11.3 PII 最小化（M-13, §9.3.1）
- `pii` は **`companyName` / `contactName` / `date` の 3 項目で固定**（CS-R1-5）。画面・印刷・匿名化処理・コピー除外対象はすべてこの定義に従う。
- 企業名・担当者名・日付入力欄は **結果画面／印刷プレビューの「企業名等を入力する」トグル（既定 閉）** を開いた時のみ表示。
- 入力欄表示時は編集フォーカス時以外マスキング表示（例 `株式会社●●●`、担当者名は `●● ●●`）。
- 印刷プレビューの「匿名化して印刷」トグル **デフォルト ON**。適用対象は `companyName` / `contactName` / `salesMemo` の 3 項目。
- `salesMemo`:
  - 画面: 結果画面の textarea（任意・デフォルト空）。
  - 印刷: **詳細版のみ**、かつ **`State.ui.printSalesMemo === true`（サブトグル ON）** のときだけ印字する（CS-R1-4）。
  - localStorage: **保存対象外**（セッションメモリのみ）。
- `pii` / `salesMemo` は localStorage から完全除外（§4.5）。

#### 11.3.2 PII 入力トグルの DOM とイベント（CS-R2-3）

| 要素 | id | 役割 | イベント |
|------|----|------|----------|
| 開閉トグル | `btn-toggle-pii` | `pii-fields` の表示/非表示を切替。初期は `aria-expanded="false"` で `#pii-fields` は `hidden` | `click` → `Render.togglePiiFields(!State.ui.piiFieldsOpen)` を呼び、`State.ui.piiFieldsOpen` を反転 |
| 入力ラッパ | `pii-fields` | 3 入力欄を内包。トグル閉時は `hidden`。印刷プレビュー側でも同 ID で再利用可 | - |
| 企業名 | `inp-company-name` (data-pii="companyName") | State.pii.companyName と双方向同期 | `input`: State 更新／`focus`: 平文表示／`blur`: マスキング表示 |
| 担当者名 | `inp-contact-name` (data-pii="contactName") | State.pii.contactName と双方向同期 | 同上 |
| 日付 | `inp-date` (data-pii="date") | State.pii.date と双方向同期（type="date"） | `input` のみ（type=date はマスキング不要） |

- トグル閉→開で入力欄は State の現値で描画され直す。閉に戻しても State の値は破棄しない（セッション内のみ保持）。
- `Render.maskPiiField(el)` はフォーカスを外した際に `el.dataset.pii` 値に応じて伏せ字文字列を表示属性として反映する（値自体は State に保持される）。
- 印刷プレビューの `#print-header-*` 要素は `ui.anonymize` に応じて平文／伏せ字を `Render.toPrint()` が書き込む（入力欄自体は `screen-print` には存在せず、結果画面側の入力結果を反映する）。

#### 11.3.1 営業メモ印字 真理値表（CS-R1-4 による固定仕様）

| 印刷モード | `ui.anonymize` | `ui.printSalesMemo` | `salesMemo` 印字 | 備考 |
|-----------|-----------------|----------------------|-------------------|------|
| summary | ON | ON | **印字しない** | 要約版では常に非印字（§10.2） |
| summary | ON | OFF | 印字しない | 同上 |
| summary | OFF | ON | 印字しない | 同上 |
| summary | OFF | OFF | 印字しない | 同上 |
| detail | ON | ON | **印字する**（匿名化適用済み） | 平文 PII は伏せ字化して印字 |
| detail | ON | OFF | 印字しない | サブトグル OFF では常に非印字 |
| detail | OFF | ON | **印字する**（平文） | 匿名化 OFF + サブトグル ON で平文印字 |
| detail | OFF | OFF | **印字しない** | 匿名化 OFF 単独ではメモが漏れないようにする（CS-R1-4 の本質） |

- 唯一の印字条件: `printMode === 'detail' && ui.printSalesMemo === true`。
- 匿名化トグル（`ui.anonymize`）は「印字するかどうか」には関与せず、印字する場合のマスキング可否のみを制御する。

### 11.4 免責常時表示（M-14）
- `#app-header` は画面表示時 sticky、全画面で常時表示。
- 印刷時は static に戻し `.disclaimer-print` を各ページ用に別実装（§10.5）。

### 11.5 禁止事項（MUST NOT、要件§5 / 設計§9.5）
- 外部通信: `fetch`, `XMLHttpRequest`, `<img src=http…>`, `<link href=http…>`, Google Fonts, CDN 読込の一切を行わない。
- 「顧客情報漏洩リスクなし」等の断定表現を文言に含めない。
- 画像はインライン SVG または CSS 描画のみ。

### 11.6 オフライン動作担保（M-10）
- index.html を file:// で開いて全機能動作することを、実装完了時のチェックリストに明記（§13.3）。
- 実装時 grep チェック: `grep -E "https?://" src/index.html` が空であること（例外: コメント内の仕様参照 URL を除く）。

---

## 12. S-04 結果サマリコピーの文字列仕様

`AppCore.onCopySummary()` は下記テンプレ（PII 非含有＝`companyName` / `contactName` / `date` / `salesMemo` を含めない）で生成。

```
【運用整備ナビゲーター 診断結果】
パターン: {patternId} {patternName}
該当理由: {reasonHighlightsJoined}
要ヒアリング: {tagsJoined or 「特になし」}
推奨工数目安: {effort}
---
本ツールは診断補助であり、法令判定ではありません。
```

- `reasonHighlightsJoined` は `軸=値` を `／` 区切りで連結（例 `L=3／A=2／拡張計画あり`）。
- clipboard API 不可時は `§9.1` のフォールバックモーダルで手動コピー。

開発者向け副機能「診断サマリ JSON をコピー」は `{ startedAt, completedAt, mode, answers, result, tags, appVersion }` を出力（PII 非含有）。

---

## 13. テスト設計

### 13.1 判定エンジン単体テスト（手動、samples/demo_answers.json で再現）

| No | 入力（answers） | mode | 期待 pattern | 期待 priority | 期待タグ |
|----|-----------------|------|--------------|---------------|----------|
| T1 | Q2=Y,Q3=Y,Q5=Y,Q12=Y,Q13=KYOTEI,Q6=NO,Q15=Y | short | **C** | 2 | 代理承認未整備(Q6), 省略項目あり |
| T2 | Q2=N,Q4=N,Q7=Y,Q12=N,Q13=KYOTEI（+他N） | full | **A** | 5 | （なし） |
| T3 | Q2=Y,Q3=Y,Q5=N,Q8=Y,Q12=N（他N/協定） | full | **D** | 3 | |
| T4 | Q2=N,Q4=Y,Q3=Y,Q7=N,Q5=Y,Q12=N（他N/協定） | full | **B** | 4 | |
| T5 | 任意に Q16=未整備 を含む | full | **E** | 1 | Q16（36協定） |
| T6 | 任意に Q17=未整備 を含む | full | **E** | 1 | Q17（抵触日） |
| T7 | Q6=NO を含むフル版回答 | full | **E** | 1 | Q6 代理承認未整備 |
| T8 | どのルールにもマッチしない境界値 | full | 最近傍 | 6 | 確定度: 中 |
| T9 (MS-R3-3) | Q12=UNKNOWN（他ショート項目 Q1/Q2/Q3/Q6/Q13 未回答） | short | **A** | 6 | Q12 わからない, 省略項目あり, 要ヒアリング（確定度: 中）※ fallback=true（`calcCShort` で C=2、`calcAShort` で A=1、L=1。`nearestPattern` が最小距離で A を返す） |
| T10 (MS-R3-3) | Q2=N,Q4=N,Q7=Y,Q12=N,Q13=UNDECIDED（他 N/協定） | full | **A** | 5 | Q13 未確定（C 不変を確認）※ C=1 のまま A 発火するケースで C 軸不変を回帰確認 |

### 13.2 UIフロー手動テスト

- **T-UI-1**: ショート版でシナリオA（要件§6.1）を完走、4分以内、C パターンが出る。
- **T-UI-2**: 質問の途中で戻る→回答が未回答に戻る→進捗バーが減る。
- **T-UI-3**: 初問で戻るボタンが disabled。`←` キーも no-op。
- **T-UI-4**: 「保存しない」で開始→localStorage にキーが**書かれていない**ことを DevTools で確認。
- **T-UI-5**: 「保存する」→切替直後に save 発火→ブラウザを一度閉じて開き直し→「続きから再開」で復元。
- **T-UI-6**: localStorage 無効化（プライベートブラウジング等）で黄バナーが出る／機能継続。
- **T-UI-7**: 結果画面から要約版を印刷→A4 1 枚で免責が必ず出る。
- **T-UI-8**: 詳細版印刷で「匿名化 ON」＋「営業メモを印字する OFF」→営業メモ非印字／企業名は伏せ字。
- **T-UI-9**: 詳細版印刷で「匿名化 OFF」＋「営業メモを印字する ON」→営業メモ印字／企業名平文。
- **T-UI-10**: フォールバック判定時、黄バッジ「確定度: 中」が出る。
- **T-UI-11** (CS-R1-1): splash 初期状態（`persist=none` 選択）で `btn-resume` が **hidden かつ disabled**。`persist=local` に切替＋`hasSavedSession()=true` の条件が揃ったときにのみ表示・活性化されることを確認。
- **T-UI-12** (CS-R1-2): 保存された回答を「続きから再開」で復元した直後に Q1 以降の回答を進めると、localStorage の該当キーが更新される（= `persistMode` が `'local'` のまま維持されており `Persist.save()` が no-op になっていない）。
- **T-UI-13** (CS-R1-3): `PATTERN_RULES` に意図的に不正値（例: `patternId:'Z'`）を注入した状態で起動すると、設定エラー黄バナーが表示され `btn-start-short` / `btn-start-full` / `btn-resume` すべてが disabled で、クリックしても反応しない。
- **T-UI-14** (CS-R1-4 真理値表): 詳細版印刷プレビューで「匿名化 ON ＋ 営業メモ OFF」「匿名化 OFF ＋ 営業メモ OFF」いずれの場合も `salesMemo` が印字されないことを確認（§11.3.1 表に完全一致すること）。
- **T-UI-15** (CS-R2-1 空セッション保存防止): splash で `persist=local` に切替直後の localStorage を確認すると `cs_yesno_diag_v1` キーが**書かれていない**。ショート版/フル版の開始ボタン押下（最初の質問表示）時点で初めてキーが書かれる。
- **T-UI-16** (MS-R2-4 破損ペイロード耐性): DevTools で `localStorage.setItem('cs_yesno_diag_v1','{"broken":true}')` を実行し、splash で「保存する」＋「続きから再開」を押しても画面は遷移せず splash のまま。`localStorage.getItem('cs_yesno_diag_v1')` が `null`（clear 済み）になっていること。
- **T-UI-17** (CS-R2-3 PII トグル DOM 存在／動作): 結果画面に `btn-toggle-pii` と `pii-fields`（`inp-company-name` / `inp-contact-name` / `inp-date`）が存在。初期状態で `pii-fields` が `hidden`、ボタン押下で表示され `aria-expanded="true"` になる。blur 時に企業名がマスキング表示（例 `株式会社●●●`）に切り替わる。
- **T-UI-18** (CS-R3-1 印刷免責の全ページ反復): 詳細版印刷で本文が 2 ページ以上になる回答パターン（例: E パターン＋営業メモ印字 ON＋長文メモ）で印刷プレビューを表示し、**2 ページ目以降にも `.disclaimer-print`「本ツールは診断補助であり、法令判定ではありません。」が表示されている**ことを確認（Chromium / WebKit / Gecko それぞれで確認）。1 ページ目本文の先頭が免責バーと重ならないこと（`body { margin-top: 14mm; }` 効果）も目視で確認する。

### 13.3 単一HTML制約検証

- **T-FILE-1**: `wc -c src/index.html` で 1MB 未満（目標 300KB 以下）。
- **T-FILE-2**: `grep -nE "https?://" src/index.html` で外部 URL が検出されないこと（コメント内の仕様参照を除く）。
- **T-FILE-3**: ネット切断状態で `file://` 経由で開き、全機能が動作する。
- **T-FILE-4**: Chrome / Edge / Safari / Firefox の最新版でそれぞれ動作確認。

### 13.4 `estimateRemaining` 単体テスト（設計§7.1.1 T1〜T3）

- **T-EST-1**: `mode='short'` では `estimateRemaining` は内部で使われない（`progress()` のショートパスを通る）。
- **T-EST-2**: フル版初回 `currentQid='Q1'`, `answers={}` で末端まで到達する正値。
- **T-EST-3**: `answers.Q1='YES'` セット後（次の Q2）は T-EST-2 より 1 少ない。

---

## 付録A. 配色と色分け指針（最終値は実装時確定）

| 要素 | CSS 変数 | 目安値 |
|------|---------|--------|
| 免責バー背景 | `--disclaimer-bg` | `#fffbe6`（薄黄） |
| 要ヒアリングバッジ | `--tag-warn` | `#f5c518` 系（黄） |
| パターンA〜E | `--pattern-a 〜 e` | 彩度を抑えた5色。印刷モノクロ時でもパターン名テキストで識別可 |
| 本文 | `--fg` | `#222` |
| 背景 | `--bg` | `#f7f7f7` |

コントラスト比 4.5:1 以上を維持（要件§5 アクセシビリティ）。

## 付録B. 実装上の決定記録（設計付録Cに追補）

| 決定事項 | 選択 | 理由 |
|---------|------|------|
| 回答値の内部表現 | 英字コード | 表示日本語とロジック比較を分離、多言語化余地 |
| QUESTIONS の格納形式 | ID キー辞書 | 分岐関数から `QUESTIONS[nextQid]` で直接参照でき保守性が高い |
| パターン判定 | `PATTERN_RULES` 単独 | 表示と判定の重複源を排除（設計§5.2.2） |
| 印刷画面の実装 | 本体と同一 DOM を `<body>` クラスで切替 | 単一ファイル・最小実装方針 |
| バリデーション | 起動時 1 度のみ | 実行時コストを避けつつ、構成エラーを早期検知 |
| `PATTERN_RULES` の優先順（1:E→2:C→3:D→4:B→5:A）を正とする（MS-R1-1） | 仕様書 §6.2 を単一ソース | 法対応要整備（E）を最優先とし派遣法免責の観点で最も慎重に扱う必要がある。次に拡張計画あり（C）、多事業所分散（D）、複数拠点（B）、基本（A）の順で顧客影響度が下がる。設計書 §5.2.2 の例示（3:B,4:A,5:D）は初期ドラフトで、実装直前フェーズの仕様書 §6.2 に収束させた |
| 営業メモ印字条件 | `State.ui.printSalesMemo===true` のみ（CS-R1-4） | 匿名化 OFF 単独でメモが漏れないよう印字条件を真理値表で固定（§11.3.1）。匿名化トグルはマスキング可否のみ担当 |
| PII の項目固定 | `companyName` / `contactName` / `date` の 3 項目（CS-R1-5） | 匿名化対象と `pii` 定義の不整合を解消。画面・印刷・コピー除外すべて同一定義に統一 |
| Q17=PART の軸扱い | 要件§10.3.2 を正とし C=3（E に昇格）（MS-R2-1） | R1 で「PART=C=2 止まり」に暫定反転したが、要件書の決定表では E 条件に「一部のみ」を明記している。要件書と仕様書の差分を放置できないため、R2 で要件書に揃えて再反転 |
| 空セッション保存防止 | `Persist.save()` 側で `mode ∈ {full,short} && currentQid` を必須化（CS-R2-1） | `none→local` 直後の save で `mode='splash' / currentQid=null` が書き込まれ `PersistPayload.mode='full'\|'short'` と矛盾する問題を解消。トグル即時 save の原則は維持しつつ、無効ペイロードは save 側で弾く |
| `Persist.load()` 妥当性検証 | 必須キー＋型チェック失敗で `clear()+false`（MS-R2-4） | 破損 JSON 復元で画面遷移が壊れるリスクを排除 |
| `PATTERNS.detail` スキーマ | `{ category, label, status }` 配列に完全定義（CS-R2-2） | 詳細版印刷チェックリストの生成元が未定義だとレンダーできない。設計§5.2 `printDetailModel.checkList` と完全一致させ、`PrintChecklistItem.status` 列（推奨/要確認/要ヒアリング）も型定義に追加（MS-R2-2） |
| `PrintAnswer.answerCode` 列 | 追加（MS-R2-2） | 設計書§5.2 の `answers[].answerCode` と揃え、内部コード（ANS.*）の印刷出力を仕様として担保 |
| 印刷免責の全ページ反復方式 | `position: fixed` + `body margin-top 14mm`（CS-R3-1） | `sticky` は初頁のみ／`thead` 複製はブラウザ差異が大きい。`fixed` は Chromium/WebKit/Gecko 共通で各ページ複製されるため、単一 HTML で JS を足さずに反復を達成できる。T-UI-18 で 2 ページ以上時の挙動を実機確認 |
| `Persist.load()` 整合チェック強化 | `currentQid in QUESTIONS` / `history` 要素検証 / `shortIndex` 範囲 / `mode='short'` 時の `currentQid===SHORT_ROUTE[shortIndex]` を必須化（MS-R3-1） | 型だけ合った壊れたデータで復元破綻するリスクを排除 |
| Render/AppCore の責務境界 | `Render.updateResumeButton(show: boolean)` に改め、判定は `AppCore.computeResumeVisibility()` に集約（MS-R3-2） | 設計§3.2「Render は State を読むのみ」を厳守。`Persist.hasSavedSession()` 等の副作用呼び出しを Render から排除 |
| ショート版の P 軸扱い | P 軸未評価（`SHORT_ROUTE` に Q1 を含まず COARSE 固定、mS-R3-1） | ショート版は 7 問に絞るため P 軸は評価しない。実装上は `a.Q1===undefined` → COARSE で確定し異常系を作らない |

---

**以上**
