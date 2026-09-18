import { http, MOCK_MODE } from './client';

export type TaskStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';

export interface DetectTask {
  id: number;
  paperTitle: string;
  status: TaskStatus;
  aiRate: number | null;
  degreeType: 'BACHELOR' | 'MASTER' | 'PHD';
  threshold: number;
  createdAt: string;
}

export interface SentenceScore {
  sentenceIdx: number;
  text: string;
  aiProb: number;
}

export interface ParagraphResult {
  paragraphIdx: number;
  text: string;
  aiProb: number;
  calibratedProb: number;
  sourceLabel: string | null;
  sentences: SentenceScore[];
}

export interface TaskDetail extends DetectTask {
  paragraphs: ParagraphResult[];
  sourceLabels: Record<string, number>;
}

// ---- mock 数据（EXPO_PUBLIC_API_BASE 未配置时启用，纯 UI 开发用）----

const mockTasks: DetectTask[] = [
  { id: 1, paperTitle: '基于深度学习的中文文本情感分析研究', status: 'DONE', aiRate: 26.4, degreeType: 'MASTER', threshold: 15, createdAt: '2026-09-16 14:20' },
  { id: 2, paperTitle: '乡村振兴背景下农产品电商发展路径研究', status: 'RUNNING', aiRate: null, degreeType: 'BACHELOR', threshold: 20, createdAt: '2026-09-17 09:12' },
  { id: 3, paperTitle: '双碳目标下制造业绿色转型机制研究', status: 'DONE', aiRate: 8.1, degreeType: 'PHD', threshold: 10, createdAt: '2026-09-15 18:44' },
];

const mockDetail: TaskDetail = {
  ...mockTasks[0],
  sourceLabels: { qwen: 0.42, gpt: 0.31, human: 0.27 },
  paragraphs: [
    {
      paragraphIdx: 0,
      text: '随着人工智能技术的快速发展，深度学习在自然语言处理领域的应用日益广泛。值得注意的是，情感分析作为其中的重要分支，已经成为学术界和工业界共同关注的焦点。',
      aiProb: 0.91,
      calibratedProb: 0.88,
      sourceLabel: 'qwen',
      sentences: [
        { sentenceIdx: 0, text: '随着人工智能技术的快速发展，深度学习在自然语言处理领域的应用日益广泛。', aiProb: 0.93 },
        { sentenceIdx: 1, text: '值得注意的是，情感分析作为其中的重要分支，已经成为学术界和工业界共同关注的焦点。', aiProb: 0.89 },
      ],
    },
    {
      paragraphIdx: 1,
      text: '我们在实验中发现，当训练数据里混入大量口语化评论时，模型在正式文本上的表现反而下降了两个点，这个现象起初让我们很困惑。',
      aiProb: 0.12,
      calibratedProb: 0.09,
      sourceLabel: 'human',
      sentences: [
        { sentenceIdx: 0, text: '我们在实验中发现，当训练数据里混入大量口语化评论时，模型在正式文本上的表现反而下降了两个点，这个现象起初让我们很困惑。', aiProb: 0.12 },
      ],
    },
  ],
};

// ---- API ----

// 路径遵循 docs/design/API_CONTRACT.md（§3-§4），移除 /mobile 前缀，与 Web 端共用

export async function listTasks(): Promise<DetectTask[]> {
  if (MOCK_MODE) return mockTasks;
  // §3.2 返回 { total, rows } 分页体，只取 rows
  const resp = await http.get('/api/v1/detect/tasks', { params: { pageNum: 1, pageSize: 50 } });
  return resp.data.data.rows;
}

export async function getTaskDetail(id: number): Promise<TaskDetail> {
  if (MOCK_MODE) return { ...mockDetail, id };
  const resp = await http.get(`/api/v1/detect/tasks/${id}`);
  return resp.data.data;
}

export async function uploadPaper(file: { uri: string; name: string; mimeType?: string }, degreeType: string): Promise<DetectTask> {
  if (MOCK_MODE) {
    return { id: Date.now(), paperTitle: file.name, status: 'PENDING', aiRate: null, degreeType: degreeType as DetectTask['degreeType'], threshold: 20, createdAt: new Date().toISOString() };
  }
  const form = new FormData();
  // @ts-expect-error RN FormData file 结构
  form.append('file', { uri: file.uri, name: file.name, type: file.mimeType ?? 'application/octet-stream' });
  form.append('degreeType', degreeType);
  // §3.1 上传端点从 /upload 改为 /submit
  const resp = await http.post('/api/v1/detect/submit', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return resp.data.data;
}

export async function requestHumanize(taskId: number, paragraphIdx: number): Promise<string> {
  if (MOCK_MODE) {
    return '人工智能近年来发展得很快，深度学习也因此被越来越多地用在自然语言处理上。情感分析是其中一个重要方向，学界和产业界都很关注它。';
  }
  const resp = await http.post(`/api/v1/humanize`, { taskId, paragraphIdx });
  return resp.data.data.rewrittenText;
}
