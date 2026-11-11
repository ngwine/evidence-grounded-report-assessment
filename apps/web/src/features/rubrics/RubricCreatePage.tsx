import { Fragment, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  breakpointsFromLevels,
  compileRubricChecklist,
  createRubric,
  getRubricDetail,
  levelsFromBreakpoints,
  updateRubricDraft,
} from "../../lib/api";
import type {
  ChecklistImportance,
  CreateRubricParams,
  RubricChecklistItem,
  RubricCriterion,
  RubricCriterionLevel,
  RubricVersionStatus,
} from "../../lib/types";
import { checklistImportanceLabel } from "../../lib/statusMaps";
import "./rubrics.css";

let idCounter = 0;
function makeId(prefix: string): string {
  idCounter += 1;
  return `${prefix}_${idCounter}`;
}

const DEFAULT_LEVEL_NAMES = ["Tốt", "Khá", "Trung bình", "Yếu"];
const MIN_LEVELS = 2;
const MAX_LEVELS = 6;

interface CriterionDraft {
  id: string;
  title: string;
  weight: string;
  /** (so muc - 1) diem chia giua cac muc, giam dan -- xem lib/api.ts levelsFromBreakpoints */
  breakpoints: string[];
  /**
   * Cung do dai voi breakpoints -- o nao GV DA TU GO (khong con trong)
   * thi true, o do duoc coi la "mot" (anchor) khi tinh lai goi y cho cac
   * o con lai, KHONG BAO GIO bi thuat toan ghi de. O nao false (con
   * trong hoac dang do thuat toan tu goi y) se duoc tinh lai moi khi co
   * thay doi -- xem computeSuggestedBreakpoints.
   */
  touchedBreakpoints: boolean[];
}

function emptyCriterion(levelCount: number): CriterionDraft {
  return {
    id: makeId("crit"),
    title: "",
    weight: "",
    breakpoints: Array.from({ length: levelCount - 1 }, () => ""),
    touchedBreakpoints: Array.from({ length: levelCount - 1 }, () => false),
  };
}

/**
 * Thuat toan goi y khoang diem (Yen yeu cau 2026-10-25 sau khi phan anh
 * ban goi y chia-deu-1-lan cu bi "ki" khi GV tu go 1 o roi cac o khac van
 * trong trong): tinh lai MOI khi trong so / so muc / 1 diem chia nao do
 * thay doi, CHIA DEU khoang cach giua 2 "moc" gan nhat da biet (trong so
 * o tren cung, cac diem chia GV da tu go -- touchedBreakpoints[i]=true,
 * va 0 o duoi cung), cho TUNG O con trong (chua tung bi GV go). O nao GV
 * da tu go thi giu nguyen, khong bao gio bi ghi de.
 *
 * Vd: trong so 10, 6 muc, GV tu go 0.8 vao o dau tien -- 4 o con lai se
 * tu chia deu tu 0.8 xuong 0: 0.64, 0.48, 0.32, 0.16 (xem moc giua 2
 * "neighbor" da biet gan nhat, khong phai chia deu tren toan bo [0,10]).
 * Khi GV CHUA go gi ca thi chi co 2 moc la trong so va 0 -- chia deu toan
 * bo pham vi, giong he thuat toan cu truoc do.
 */
function computeSuggestedBreakpoints(
  weight: number,
  breakpoints: string[],
  touched: boolean[],
): string[] {
  const count = breakpoints.length;
  const anchors: Array<{ pos: number; value: number }> = [{ pos: -1, value: weight }];
  breakpoints.forEach((raw, i) => {
    if (!touched[i]) return;
    const value = Number(raw);
    if (raw.trim() !== "" && !Number.isNaN(value)) anchors.push({ pos: i, value });
  });
  anchors.push({ pos: count, value: 0 });
  anchors.sort((a, b) => a.pos - b.pos);

  const result = [...breakpoints];
  for (let a = 0; a < anchors.length - 1; a++) {
    const left = anchors[a];
    const right = anchors[a + 1];
    const steps = right.pos - left.pos;
    for (let pos = left.pos + 1; pos < right.pos; pos++) {
      if (touched[pos]) continue;
      const t = (pos - left.pos) / steps;
      const raw = left.value + (right.value - left.value) * t;
      result[pos] = String(Math.round(raw * 10) / 10);
    }
  }
  return result;
}

type Step = "CRITERIA" | "CHECKLIST";

/**
 * Man "Tao rubric" -- buoc 1: giang vien nhap tieu de rubric, chon ten
 * cac muc do danh gia DUNG CHUNG cho moi tieu chi (2-6 muc, vd Tot/Kha/
 * Trung binh/Yeu -- theo docs/rubric/rubric-v1.md muc 2), roi voi tung
 * tieu chi chi can nhap trong so + cac DIEM CHIA giua cac muc (khong can
 * tu nhap [min,max] hay hieu khai niem nua-mo/dong, he thong tu suy ra --
 * xem lib/api.ts levelsFromBreakpoints). Bam "Tao rubric" se goi Rubric
 * Compiler (mock, xem lib/api.ts) de tach thanh checklist (co tu doan
 * nhan do quan trong Cot loi/Bat buoc/Khong bat buoc), chuyen sang buoc 2
 * cho giang vien xem/sua/xac nhan. Dat trong features/rubrics rieng
 * (khong chung voi features/review) theo yeu cau "rubric dung folder
 * rieng, giong workspace".
 */
export function RubricCreatePage() {
  const { workspaceId, rubricId } = useParams<{ workspaceId: string; rubricId?: string }>();
  const navigate = useNavigate();
  const isEditMode = Boolean(rubricId);

  const [step, setStep] = useState<Step>("CRITERIA");
  const [title, setTitle] = useState("");
  const [levelNames, setLevelNames] = useState<string[]>(DEFAULT_LEVEL_NAMES);
  const [criteria, setCriteria] = useState<CriterionDraft[]>([
    emptyCriterion(DEFAULT_LEVEL_NAMES.length),
  ]);
  const [compiledCriteria, setCompiledCriteria] = useState<RubricCriterion[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // Card tieu chi nao dang thu gon (Collapse/Expand) -- mac dinh moi card
  // deu mo, chi thu gon khi GV tu bam.
  const [collapsedCriteriaIds, setCollapsedCriteriaIds] = useState<Set<string>>(new Set());

  // --- Che do SUA 1 rubric da co (isEditMode) -- Yen yeu cau 2026-10-27
  // "gio minh lam phan sua di, giao dien quay lai giong luc tao rubric
  // ha?". CHI cho sua khi version hien tai la DRAFT (xem updateRubricDraft
  // trong lib/api.ts). `loadState` = "LOADING" khi dang cho fetch (chi
  // dung khi isEditMode), "READY" khi khong can load (tao moi) hoac da
  // load xong, "NOT_FOUND"/"NOT_DRAFT" khi khong sua duoc.
  const [loadState, setLoadState] = useState<"LOADING" | "READY" | "NOT_FOUND" | "NOT_DRAFT">(
    isEditMode ? "LOADING" : "READY",
  );
  // Checklist GV da tung nhap cho tung tieu chi co san (khoa bang CHINH id
  // cua CriterionDraft duoc tao khi load, xem buildParams/handleCompile) --
  // giu lai de KHONG bi Rubric Compiler ghi de mat khi GV quay lai sua.
  const [existingChecklistsByDraftId, setExistingChecklistsByDraftId] = useState<
    Record<string, RubricChecklistItem[]>
  >({});

  useEffect(() => {
    if (!isEditMode || !rubricId) return;
    let cancelled = false;

    getRubricDetail(rubricId).then((detail) => {
      if (cancelled) return;
      if (!detail) {
        setLoadState("NOT_FOUND");
        return;
      }
      if (detail.version.status !== "DRAFT") {
        setLoadState("NOT_DRAFT");
        return;
      }

      const checklistsByDraftId: Record<string, RubricChecklistItem[]> = {};
      const nextCriteria: CriterionDraft[] = detail.version.criteria.map((criterion) => {
        const breakpoints = breakpointsFromLevels(criterion.levels).map(String);
        const draft: CriterionDraft = {
          id: makeId("crit"),
          title: criterion.title,
          weight: String(criterion.weight),
          breakpoints,
          // Cac diem chia nay la gia tri THAT da luu, khong phai goi y --
          // danh dau touched=true de thuat toan goi y khong dung len sua.
          touchedBreakpoints: breakpoints.map(() => true),
        };
        checklistsByDraftId[draft.id] = criterion.checklists;
        return draft;
      });

      setTitle(detail.rubric.title);
      setLevelNames(detail.version.level_names);
      setCriteria(
        nextCriteria.length > 0 ? nextCriteria : [emptyCriterion(detail.version.level_names.length)],
      );
      setExistingChecklistsByDraftId(checklistsByDraftId);
      setLoadState("READY");
    });

    return () => {
      cancelled = true;
    };
  }, [isEditMode, rubricId]);

  if (!workspaceId) return null;
  // TS khong giu duoc narrowing cua workspaceId ben trong cac closure
  // (buildParams/handleConfirm...) duoc khai bao phia duoi -- gan lai 1
  // const rieng de cac ham do dung, khoi phai "!" ep kieu lai nhieu lan.
  const safeWorkspaceId: string = workspaceId;

  if (loadState === "LOADING") {
    return (
      <section className="panel">
        <p className="panel__hint">Đang tải...</p>
      </section>
    );
  }

  if (loadState === "NOT_FOUND" || loadState === "NOT_DRAFT") {
    return (
      <section className="panel">
        <p className="panel__hint">
          {loadState === "NOT_FOUND"
            ? "Không tìm thấy rubric này, hoặc bạn không có quyền sửa."
            : "Rubric này đã công bố nên không thể sửa trực tiếp — muốn thay đổi phải tạo phiên bản mới (chưa hỗ trợ)."}
        </p>
        {rubricId && (
          <Link
            className="link-button"
            to={`/lecturer/workspaces/${safeWorkspaceId}/rubrics/${rubricId}`}
          >
            Quay lại xem rubric
          </Link>
        )}
      </section>
    );
  }

  const totalWeight = criteria.reduce((sum, c) => sum + (Number(c.weight) || 0), 0);

  /**
   * Suy ra [min,max] tung muc de hien thi preview song khi GV dang nhap
   * o Buoc 1 (dung chung 1 ham voi lib/api.ts de khong lech logic) --
   * tra ve null neu trong so/diem chia chua nhap du/hop le, de bang
   * preview hien "—" thay vi crash.
   */
  /** GV cần nhập trọng số hợp lệ trước thì mới chia khoảng điểm cho từng mức được (vì mức Tốt phải chạm đúng trọng số). */
  function hasValidWeight(criterion: CriterionDraft): boolean {
    const weightNum = Number(criterion.weight);
    return criterion.weight.trim() !== "" && !Number.isNaN(weightNum) && weightNum > 0;
  }

  function previewLevels(criterion: CriterionDraft): RubricCriterionLevel[] | null {
    const weightNum = Number(criterion.weight);
    if (!criterion.weight.trim() || Number.isNaN(weightNum) || weightNum <= 0) return null;

    const breakpointNums: number[] = [];
    let previous = weightNum;
    for (const raw of criterion.breakpoints) {
      const value = Number(raw);
      if (!raw.trim() || Number.isNaN(value) || value <= 0 || value >= previous) return null;
      breakpointNums.push(value);
      previous = value;
    }

    return levelsFromBreakpoints(weightNum, breakpointNums);
  }

  function setLevelCount(nextCount: number) {
    setLevelNames((prev) => {
      const next = [...prev];
      while (next.length < nextCount) next.push(`Mức ${next.length + 1}`);
      return next.slice(0, nextCount);
    });
    setCriteria((prev) =>
      prev.map((c) => {
        const nextBreakpoints = [...c.breakpoints];
        const nextTouched = [...c.touchedBreakpoints];
        while (nextBreakpoints.length < nextCount - 1) {
          nextBreakpoints.push("");
          nextTouched.push(false);
        }
        const resized = {
          ...c,
          breakpoints: nextBreakpoints.slice(0, nextCount - 1),
          touchedBreakpoints: nextTouched.slice(0, nextCount - 1),
        };
        const weightNum = Number(resized.weight);
        if (!resized.weight.trim() || Number.isNaN(weightNum) || weightNum <= 0) return resized;
        return {
          ...resized,
          breakpoints: computeSuggestedBreakpoints(
            weightNum,
            resized.breakpoints,
            resized.touchedBreakpoints,
          ),
        };
      }),
    );
  }

  function updateLevelName(index: number, value: string) {
    setLevelNames((prev) => prev.map((name, i) => (i === index ? value : name)));
  }

  function updateCriterion(id: string, patch: Partial<CriterionDraft>) {
    setCriteria((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)));
  }

  /**
   * Nhap Trong so: cap nhat gia tri VA tinh lai goi y cho MOI o diem chia
   * con trong (chua tung bi GV go) NGAY TREN TUNG PHIM GO (khong doi den
   * onBlur nua -- Yen phan anh 2026-10-25 la doi den luc bam ra ngoai moi
   * cap nhat nhin "ki", hien thi khoang diem cu trong luc dang go). Thuat
   * toan moi (computeSuggestedBreakpoints) an toan de goi lien tuc nhu
   * vay: no LUON tinh lai tu dau dua tren trong so hien tai, khong con
   * conditon "chi tu dien 1 lan dau" nhu ban cu (ban cu moi bi loi goi 1
   * lan voi gia tri trong so chua go xong, vd go "10" bi tinh nham voi
   * trong so = "1" truoc do).
   */
  function handleWeightChange(criterionId: string, value: string) {
    setCriteria((prev) =>
      prev.map((c) => {
        if (c.id !== criterionId) return c;
        const weightNum = Number(value);
        if (!value.trim() || Number.isNaN(weightNum) || weightNum <= 0) {
          return { ...c, weight: value };
        }
        return {
          ...c,
          weight: value,
          breakpoints: computeSuggestedBreakpoints(weightNum, c.breakpoints, c.touchedBreakpoints),
        };
      }),
    );
  }

  /**
   * Tinh lai goi y cho MOI o diem chia con trong (chua tung bi GV go) cua
   * 1 tieu chi -- goi khi GV ROI KHOI (onBlur) 1 o diem chia nao do (vi du
   * GV tu go 1 o thi cac o con lai can tinh lai theo moc moi). Khong goi
   * tren moi phim go (onChange) cua O DIEM CHIA de khong "danh nhau" voi
   * GV dang go so do do (truong hop nay khac Trong so o tren -- 1 o diem
   * chia dang go co the chinh la 1 "moc" cho cac o khac, nen can go xong
   * (blur) moi dung lam moc, khong the dung ngay tung ky tu dang go).
   */
  function recomputeCriterionSuggestions(criterionId: string) {
    setCriteria((prev) =>
      prev.map((c) => {
        if (c.id !== criterionId) return c;
        const weightNum = Number(c.weight);
        if (!c.weight.trim() || Number.isNaN(weightNum) || weightNum <= 0) return c;
        return {
          ...c,
          breakpoints: computeSuggestedBreakpoints(weightNum, c.breakpoints, c.touchedBreakpoints),
        };
      }),
    );
  }

  function addCriterion() {
    setCriteria((prev) => [...prev, emptyCriterion(levelNames.length)]);
  }

  function duplicateCriterion(id: string) {
    setCriteria((prev) => {
      const index = prev.findIndex((c) => c.id === id);
      if (index === -1) return prev;
      const copy: CriterionDraft = {
        ...prev[index],
        id: makeId("crit"),
        breakpoints: [...prev[index].breakpoints],
        touchedBreakpoints: [...prev[index].touchedBreakpoints],
      };
      const next = [...prev];
      next.splice(index + 1, 0, copy);
      return next;
    });
  }

  // Hoi xac nhan truoc khi xoa -- Yen phan anh 2026-10-26 "bam nham a",
  // vi thao tac nay mat het du lieu (ten, trong so, khoang diem) cua ca 1
  // tieu chi ma khong undo duoc.
  function removeCriterion(id: string, title: string) {
    if (criteria.length <= 1) return;
    const label = title.trim() || "(chưa đặt tên)";
    const confirmed = window.confirm(
      "Xoá tiêu chí \"" + label + "\"? Toàn bộ dữ liệu của tiêu chí này (trọng số, khoảng điểm) sẽ mất.",
    );
    if (!confirmed) return;
    setCriteria((prev) => prev.filter((c) => c.id !== id));
  }

  function toggleCriterionCollapse(id: string) {
    setCollapsedCriteriaIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  /** GV tu go 1 o diem chia -- danh dau "touched" (go != trong) de thuat toan goi y khong bao gio ghi de o nay nua, tru khi GV tu xoa trong lai. */
  function updateBreakpoint(criterionId: string, breakpointIndex: number, value: string) {
    setCriteria((prev) =>
      prev.map((c) =>
        c.id !== criterionId
          ? c
          : {
              ...c,
              breakpoints: c.breakpoints.map((b, i) => (i === breakpointIndex ? value : b)),
              touchedBreakpoints: c.touchedBreakpoints.map((t, i) =>
                i === breakpointIndex ? value.trim() !== "" : t,
              ),
            },
      ),
    );
  }

  function buildParams(): CreateRubricParams | null {
    if (!title.trim()) {
      setErrorMessage("Vui lòng nhập tiêu đề rubric.");
      return null;
    }

    if (levelNames.some((name) => !name.trim())) {
      setErrorMessage("Mỗi mức độ cần có tên.");
      return null;
    }

    for (const c of criteria) {
      if (!c.title.trim()) {
        setErrorMessage("Mỗi tiêu chí cần có tên.");
        return null;
      }
      const weightNum = Number(c.weight);
      if (!c.weight.trim() || Number.isNaN(weightNum) || weightNum <= 0) {
        setErrorMessage(`Trọng số của tiêu chí "${c.title}" phải là số lớn hơn 0.`);
        return null;
      }

      let previous = weightNum;
      for (const raw of c.breakpoints) {
        const value = Number(raw);
        if (!raw.trim() || Number.isNaN(value)) {
          setErrorMessage(`Mỗi điểm chia mức của tiêu chí "${c.title}" cần là số hợp lệ.`);
          return null;
        }
        if (value <= 0 || value >= previous) {
          setErrorMessage(
            `Điểm chia mức của tiêu chí "${c.title}" phải giảm dần và nằm trong (0, ${weightNum}).`,
          );
          return null;
        }
        previous = value;
      }
    }

    return {
      workspaceId: safeWorkspaceId,
      title: title.trim(),
      levelNames: levelNames.map((n) => n.trim()),
      criteria: criteria.map((c) => ({
        title: c.title.trim(),
        weight: Number(c.weight),
        breakpoints: c.breakpoints.map(Number),
      })),
    };
  }

  async function handleCompile() {
    const params = buildParams();
    if (!params) return;

    setErrorMessage(null);
    setIsSubmitting(true);
    const result = await compileRubricChecklist(params);
    setIsSubmitting(false);
    // Che do SUA: giu lai checklist GV da tung nhap cho cac tieu chi CO
    // SAN tu luc load (khop theo dung thu tu voi criteria state, vi ca
    // buildParams() lan compileRubricChecklist deu duyet theo thu tu do
    // -- xem existingChecklistsByDraftId o tren), thay vi de Rubric
    // Compiler sinh lai 1 checklist mac dinh trong roc moi lan vao buoc
    // 2. Tieu chi MOI them trong luc sua van duoc sinh checklist mac
    // dinh binh thuong.
    const merged = result.map((compiledCriterion, index) => {
      const draftId = criteria[index]?.id;
      const existingChecklists = draftId ? existingChecklistsByDraftId[draftId] : undefined;
      return existingChecklists && existingChecklists.length > 0
        ? { ...compiledCriterion, checklists: existingChecklists }
        : compiledCriterion;
    });
    setCompiledCriteria(merged);
    setStep("CHECKLIST");
  }

  function updateChecklistCondition(criterionId: string, checklistId: string, condition: string) {
    setCompiledCriteria((prev) =>
      prev.map((c) =>
        c._id !== criterionId
          ? c
          : {
              ...c,
              checklists: c.checklists.map((cl) =>
                cl._id === checklistId ? { ...cl, condition } : cl,
              ),
            },
      ),
    );
  }

  // Khong co updateChecklistMode -- LOCAL/GRAPH do Rubric Compiler (he thong)
  // tu phan loai dua vao noi dung checklist (FR-RUB-03, docs/week-01/
  // W1-03-dac-ta-yeu-cau-v1.md), GV KHONG duoc chon tay. GV chi sua duoc
  // "importance" (Yen phan anh 2026-10-25: "gv ko co dinh nghia, ho chi
  // dinh nghia bat buoc hay ko thui, local hay graph se do he thong xac
  // dinh"). O ban demo nay mode luon la "LOCAL" (dat bang compileRubricChecklist
  // / addChecklistItem) vi logic phan loai that chua duoc cai dat.

  function updateChecklistImportance(
    criterionId: string,
    checklistId: string,
    importance: ChecklistImportance,
  ) {
    setCompiledCriteria((prev) =>
      prev.map((c) =>
        c._id !== criterionId
          ? c
          : {
              ...c,
              checklists: c.checklists.map((cl) =>
                cl._id === checklistId ? { ...cl, importance } : cl,
              ),
            },
      ),
    );
  }

  /**
   * Buoc 2: giang vien tu them 1 checklist moi cho 1 tieu chi (ngoai cai
   * compileRubricChecklist da tu sinh san) -- Yen yeu cau 2026-10-25, vi
   * Rubric Compiler chi tach 1 checklist mac dinh/tieu chi, GV co the can
   * them dieu kien kiem tra khac. Dien gia tri rong/mac dinh, GV tu sua
   * ngay ben duoi (giong cach criteria.map o Buoc 1 render form trong).
   */
  function addChecklistItem(criterionId: string) {
    setCompiledCriteria((prev) =>
      prev.map((c) => {
        if (c._id !== criterionId) return c;
        const newItem: RubricChecklistItem = {
          _id: makeId("cl"),
          checklist_key: `${c.criterion_key}_${c.checklists.length + 1}`,
          criterion_key: c.criterion_key,
          condition: "",
          mode: "LOCAL",
          importance: "REQUIRED",
        };
        return { ...c, checklists: [...c.checklists, newItem] };
      }),
    );
  }

  /** Xoa 1 checklist -- giu toi thieu 1 checklist/tieu chi (giong quy uoc removeCriterion o Buoc 1). */
  function removeChecklistItem(criterionId: string, checklistId: string) {
    setCompiledCriteria((prev) =>
      prev.map((c) => {
        if (c._id !== criterionId || c.checklists.length <= 1) return c;
        return { ...c, checklists: c.checklists.filter((cl) => cl._id !== checklistId) };
      }),
    );
  }

  // GV duoc chon luu nhap (DRAFT, con sua duoc, chua dung de cham) hay
  // cong bo luon (PUBLISHED, immutable tu do) -- dung UC-03
  // (W1-04-bo-use-case.md muc 7.3: "GV publish rubric version; version nay
  // tro thanh immutable" -- ngu y day la 1 buoc CHU DONG rieng, khong tu
  // dong publish ngay luc tao). Yen yeu cau 2026-10-26.
  async function handleConfirm(status: RubricVersionStatus) {
    const params = buildParams();
    if (!params) return;

    setIsSubmitting(true);
    const rubric =
      isEditMode && rubricId
        ? await updateRubricDraft(rubricId, params, compiledCriteria, status)
        : await createRubric(params, compiledCriteria, status);
    setIsSubmitting(false);
    // Dieu huong thang den trang xem chi tiet rubric vua tao/sua (thay vi
    // ve lai Chi tiet lop) -- Yen phan anh 2026-10-25 la bam "Xac nhan
    // hoan tat" xong khong thay gi khac tren man hinh, tuong nhu chua luu;
    // cho GV xem lai NGAY la cach xac nhan truc quan nhat la da luu that.
    navigate(`/lecturer/workspaces/${safeWorkspaceId}/rubrics/${rubric._id}`);
  }

  return (
    <section className="panel">
      <nav className="breadcrumb" aria-label="breadcrumb">
        <Link to={`/lecturer/workspaces/${safeWorkspaceId}`}>Chi tiết lớp</Link>
        <span aria-hidden="true"> &gt; </span>
        <span>{isEditMode ? "Sửa rubric" : "Tạo rubric"}</span>
      </nav>

      <h1 className="panel__title">{isEditMode ? "Sửa rubric" : "Tạo rubric"}</h1>
      <p className="panel__subtitle">
        {step === "CRITERIA"
          ? "Bước 1/2 — Nhập tiêu chí, trọng số và điểm chia giữa các mức."
          : "Bước 2/2 — Xem lại checklist được tách tự động, chỉnh sửa nếu cần rồi xác nhận."}
      </p>

      {/* Doi "Quay lai chinh tieu chi" len dau trang (canh tieu de), thay vi
          chi nam duoi cung o buoc 2 -- Yen yeu cau 2026-10-26: "y la tren
          doan Tao rubric luon a" (muon no nam o tren cung, khong phai o o
          cuoi trang canh nut Luu nhap/Cong bo). */}
      {step === "CHECKLIST" && (
        <button
          type="button"
          className="link-button rubric-form__back-top"
          disabled={isSubmitting}
          onClick={() => setStep("CRITERIA")}
        >
          ← Quay lại chỉnh tiêu chí
        </button>
      )}

      {errorMessage && <p className="rubric-form__error">{errorMessage}</p>}

      {step === "CRITERIA" && (
        <>
          <div className="rubric-header-row">
            <label className="modal__field rubric-header-row__title">
              <span className="modal__label">Tiêu đề rubric</span>
              <input
                className="modal__input"
                type="text"
                placeholder="Vd: Rubric báo cáo giữa kỳ"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>

            <label className="modal__field rubric-header-row__level-count">
              <span className="modal__label">Số mức độ (dùng chung cho mọi tiêu chí)</span>
              <select
                className="modal__input"
                value={levelNames.length}
                onChange={(event) => setLevelCount(Number(event.target.value))}
              >
                {Array.from(
                  { length: MAX_LEVELS - MIN_LEVELS + 1 },
                  (_, i) => MIN_LEVELS + i,
                ).map((n) => (
                  <option key={n} value={n}>
                    {n} mức
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="rubric-level-pills">
            <span className="modal__label">Tên mức (từ tốt nhất đến kém nhất)</span>
            <div className="rubric-level-pills__row">
              {levelNames.map((name, index) => (
                <Fragment key={index}>
                  <input
                    className="rubric-level-pill"
                    type="text"
                    value={name}
                    aria-label={`Tên mức ${index + 1}`}
                    onChange={(event) => updateLevelName(index, event.target.value)}
                  />
                  {index < levelNames.length - 1 && (
                    <span className="rubric-level-pills__arrow" aria-hidden="true">
                      →
                    </span>
                  )}
                </Fragment>
              ))}
            </div>
          </div>

          <div className="rubric-total-weight-badge">
            <span className="rubric-total-weight-badge__label">Tổng trọng số hiện tại</span>
            <span className="rubric-total-weight-badge__value">{totalWeight}</span>
          </div>

          {criteria.map((criterion, index) => {
            const isCollapsed = collapsedCriteriaIds.has(criterion.id);
            return (
              <div className="rubric-criterion-card" key={criterion.id}>
                <div className="rubric-criterion-card__header">
                  <button
                    type="button"
                    className="rubric-criterion-card__collapse-toggle"
                    onClick={() => toggleCriterionCollapse(criterion.id)}
                    aria-expanded={!isCollapsed}
                  >
                    <span
                      className={`doc-row__chevron${isCollapsed ? "" : " doc-row__chevron--open"}`}
                      aria-hidden="true"
                    >
                      ▶
                    </span>
                    <strong>
                      Tiêu chí {index + 1}
                      {criterion.title.trim() ? ` — ${criterion.title.trim()}` : ""}
                    </strong>
                  </button>
                  <div className="rubric-criterion-card__actions">
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => duplicateCriterion(criterion.id)}
                    >
                      Nhân bản
                    </button>
                    {criteria.length > 1 && (
                      <button
                        type="button"
                        className="link-button rubric-criterion-card__remove"
                        onClick={() => removeCriterion(criterion.id, criterion.title)}
                      >
                        Xoá tiêu chí
                      </button>
                    )}
                  </div>
                </div>

                {!isCollapsed && (
                  <>
                    <div className="rubric-criterion-card__row">
                      <label className="modal__field rubric-criterion-card__title-field">
                        <span className="modal__label">Tên tiêu chí</span>
                        <input
                          className="modal__input"
                          type="text"
                          placeholder="Vd: Phương pháp luận"
                          value={criterion.title}
                          onChange={(event) =>
                            updateCriterion(criterion.id, { title: event.target.value })
                          }
                        />
                      </label>
                      <label className="modal__field rubric-criterion-card__weight-field">
                        <span className="modal__label">Trọng số</span>
                        <input
                          className="modal__input"
                          type="number"
                          min="0"
                          step="0.1"
                          placeholder="Vd: 2"
                          value={criterion.weight}
                          onChange={(event) => handleWeightChange(criterion.id, event.target.value)}
                        />
                      </label>
                    </div>

                    <span className="modal__label">Khoảng điểm từng mức</span>
                    {hasValidWeight(criterion) ? (
                      <RubricLevelMatrix
                        levelNames={levelNames}
                        criterion={criterion}
                        onChangeBreakpoint={(breakpointIndex, value) =>
                          updateBreakpoint(criterion.id, breakpointIndex, value)
                        }
                        onBlurBreakpoint={() => recomputeCriterionSuggestions(criterion.id)}
                      />
                    ) : (
                      <p className="rubric-level-input-table__hint">
                        Nhập trọng số trước để chia khoảng điểm cho từng mức.
                      </p>
                    )}
                  </>
                )}
              </div>
            );
          })}

          <button type="button" className="btn-secondary rubric-form__add-criterion" onClick={addCriterion}>
            + Thêm tiêu chí
          </button>

          <div className="rubric-review-table-wrap">
            <span className="modal__label">Xem trước bảng rubric</span>
            <table className="rubric-review-table">
              <thead>
                <tr>
                  <th>Tiêu chí</th>
                  <th>Trọng số</th>
                  {levelNames.map((name, index) => (
                    <th key={index}>{name || `Mức ${index + 1}`}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {criteria.map((criterion, index) => {
                  const levels = previewLevels(criterion);
                  return (
                    <tr key={criterion.id}>
                      <td>{criterion.title.trim() || `Tiêu chí ${index + 1}`}</td>
                      <td>{criterion.weight.trim() || "—"}</td>
                      {levelNames.map((_, levelIndex) => (
                        <td key={levelIndex}>
                          {levels ? `${levels[levelIndex].min} – ${levels[levelIndex].max}` : "—"}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td>Tổng</td>
                  <td>{totalWeight}</td>
                  <td colSpan={levelNames.length} />
                </tr>
              </tfoot>
            </table>
          </div>

          <div className="rubric-form__actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={() =>
                navigate(
                  isEditMode && rubricId
                    ? `/lecturer/workspaces/${safeWorkspaceId}/rubrics/${rubricId}`
                    : `/lecturer/workspaces/${safeWorkspaceId}`,
                )
              }
            >
              Hủy
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={isSubmitting}
              onClick={handleCompile}
            >
              {isSubmitting ? "Đang tách checklist..." : isEditMode ? "Tiếp tục" : "Tạo rubric"}
            </button>
          </div>
        </>
      )}

      {step === "CHECKLIST" && (
        <>
          {compiledCriteria.map((criterion) => (
            <div className="rubric-criterion-card" key={criterion._id}>
              <div className="rubric-criterion-card__header">
                <strong>
                  {criterion.title}{" "}
                  <span className="rubric-criterion-card__weight">(trọng số {criterion.weight})</span>
                </strong>
              </div>

              {criterion.checklists.map((checklist, checklistIndex) => (
                <div className="rubric-checklist-row" key={checklist._id}>
                  <span className="rubric-checklist-row__index">{checklistIndex + 1}.</span>
                  <input
                    className="modal__input rubric-checklist-row__condition"
                    type="text"
                    placeholder="Nhập nội dung checklist..."
                    value={checklist.condition}
                    onChange={(event) =>
                      updateChecklistCondition(criterion._id, checklist._id, event.target.value)
                    }
                  />
                  {/* LOCAL/GRAPH la ket qua he thong tu phan loai (xem ghi chu o
                      updateChecklistImportance) -- khong hien ra UI, GV chi can
                      thay "importance" la du (Yen yeu cau 2026-10-26: "ko hien
                      thi local/graph o UI"). */}
                  <select
                    className="class-detail__status-select"
                    value={checklist.importance}
                    onChange={(event) =>
                      updateChecklistImportance(
                        criterion._id,
                        checklist._id,
                        event.target.value as ChecklistImportance,
                      )
                    }
                  >
                    {(Object.keys(checklistImportanceLabel) as ChecklistImportance[]).map((key) => (
                      <option key={key} value={key}>
                        {checklistImportanceLabel[key].label}
                      </option>
                    ))}
                  </select>
                  {criterion.checklists.length > 1 && (
                    <button
                      type="button"
                      className="rubric-checklist-row__remove"
                      onClick={() => removeChecklistItem(criterion._id, checklist._id)}
                      aria-label="Xoá checklist này"
                      title="Xoá checklist này"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}

              <button
                type="button"
                className="link-button rubric-checklist-row__add"
                onClick={() => addChecklistItem(criterion._id)}
              >
                + Thêm checklist
              </button>
            </div>
          ))}

          <p className="panel__hint rubric-form__publish-hint">
            Lưu nháp: còn sửa lại được, chưa dùng để chấm điểm. Công bố: khoá
            lại (không sửa trực tiếp), muốn thay đổi phải tạo phiên bản mới.
          </p>

          <div className="rubric-form__actions">
            <button
              type="button"
              className="btn-secondary"
              disabled={isSubmitting}
              onClick={() => handleConfirm("DRAFT")}
            >
              {isSubmitting ? "Đang lưu..." : "Lưu nháp"}
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={isSubmitting}
              onClick={() => handleConfirm("PUBLISHED")}
            >
              {isSubmitting ? "Đang lưu..." : "Công bố rubric"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

/**
 * Nhan min/max (dang chuoi, de hien thi) cua 1 cot muc trong bang ma
 * tran -- dung chung cho ca tieu de cot (ky hieu ngoac) va than bang (o
 * input/fixed). Muc cao nhat (levelIndex=0) dong 2 dau (min la o nhap,
 * max = dung trong so); cac muc con lai dong o min, ho o max (xem
 * docs/rubric/rubric-notes-ui-data.md). Fallback "…" (thay vi "?" cu, Yen
 * phan anh 2026-10-24 la "?" gay boi roi) chi con xay ra khi GV chu dong
 * xoa trong 1 o -- binh thuong goi y (xem computeSuggestedBreakpoints) da dien
 * san het nen hau nhu khong con gap truong hop nay.
 */
function levelBoundaryLabels(
  criterion: CriterionDraft,
  levelIndex: number,
  levelCount: number,
): { minLabel: string; maxLabel: string; isTop: boolean } {
  const isTop = levelIndex === 0;
  const isBottom = levelIndex === levelCount - 1;
  const minLabel = isBottom ? "0" : criterion.breakpoints[levelIndex]?.trim() || "…";
  const maxLabel = isTop
    ? criterion.weight.trim() || "…"
    : criterion.breakpoints[levelIndex - 1]?.trim() || "…";
  return { minLabel, maxLabel, isTop };
}

/**
 * Bang ma tran "Khoang diem tung muc" -- moi muc 1 cot, 2 o [Can duoi] -
 * [Can tren]. Theo yeu cau cua Yen 2026-10-24: quay lai kieu bang nay
 * (thay vi thuoc do lien tuc truoc do). Diem chia duoc GOI Y song (xem
 * computeSuggestedBreakpoints/recomputeCriterionSuggestions o component
 * cha, kich hoat luc GV roi khoi o Trong so hoac 1 o diem chia) -- o nao
 * GV CHUA TU GO (touchedBreakpoints[i]=false) nhung da co gia tri goi y
 * thi hien NHAT MAU HON (class --suggested) de phan biet voi o GV da tu
 * nhap, giup GV biet day chi la goi y, van sua lai duoc binh thuong.
 * Dong ky hieu ngoac vuong/tron duoi ten moi cot giup GV khong nham
 * khoang nua mo/dong.
 */
function RubricLevelMatrix({
  levelNames,
  criterion,
  onChangeBreakpoint,
  onBlurBreakpoint,
}: {
  levelNames: string[];
  criterion: CriterionDraft;
  onChangeBreakpoint: (breakpointIndex: number, value: string) => void;
  onBlurBreakpoint: () => void;
}) {
  return (
    <table className="rubric-level-input-table">
      <thead>
        <tr>
          {levelNames.map((levelName, levelIndex) => {
            const { minLabel, maxLabel, isTop } = levelBoundaryLabels(
              criterion,
              levelIndex,
              levelNames.length,
            );
            return (
              <th key={levelIndex}>
                <span className="rubric-level-input-table__name">
                  {levelName.trim() || `Mức ${levelIndex + 1}`}
                </span>
                <span className="rubric-level-input-table__range">
                  {isTop ? `[${minLabel}, ${maxLabel}]` : `[${minLabel}, ${maxLabel})`}
                </span>
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        <tr>
          {levelNames.map((_, levelIndex) => {
            const { maxLabel, isTop } = levelBoundaryLabels(criterion, levelIndex, levelNames.length);
            const isBottom = levelIndex === levelNames.length - 1;
            const isSuggested =
              !isBottom &&
              !criterion.touchedBreakpoints[levelIndex] &&
              criterion.breakpoints[levelIndex]?.trim() !== "";
            return (
              <td key={levelIndex} className="rubric-level-input-table__cell">
                {isBottom ? (
                  <span className="rubric-level-input-table__fixed">0</span>
                ) : (
                  <input
                    className={`modal__input rubric-level-input-table__input${
                      isSuggested ? " rubric-level-input-table__input--suggested" : ""
                    }`}
                    type="number"
                    step="0.1"
                    title={isSuggested ? "Giá trị gợi ý — bạn có thể sửa lại" : undefined}
                    value={criterion.breakpoints[levelIndex]}
                    onChange={(event) => onChangeBreakpoint(levelIndex, event.target.value)}
                    onBlur={onBlurBreakpoint}
                  />
                )}
                <span className="rubric-level-input-table__dash">–</span>
                {isTop ? (
                  <span className="rubric-level-input-table__fixed">{criterion.weight.trim()}</span>
                ) : (
                  <span className="rubric-level-input-table__fixed">{maxLabel}</span>
                )}
              </td>
            );
          })}
        </tr>
      </tbody>
    </table>
  );
}
