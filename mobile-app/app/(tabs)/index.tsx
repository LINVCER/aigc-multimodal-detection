import { View, Text, FlatList, Pressable, Image, StyleSheet, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { listTasks, type DetectTask } from '@/api/detect';

const STATUS_LABEL: Record<DetectTask['status'], { text: string; color: string }> = {
  PENDING: { text: '排队中', color: '#9ca3af' },
  RUNNING: { text: '检测中', color: '#f59e0b' },
  DONE: { text: '已完成', color: '#10b981' },
  FAILED: { text: '失败', color: '#ef4444' },
};

const DEGREE_LABEL: Record<string, string> = { BACHELOR: '本科', MASTER: '硕士', PHD: '博士' };
const SCENARIO_LABEL: Record<string, string> = { academic_bachelor: '本科', academic_master: '硕士', academic_phd: '博士', job_report: '职业报告', self_media: '自媒体', other: '其他' };
const sceneOf = (t: DetectTask) => (t.scenario && SCENARIO_LABEL[t.scenario]) || (t.degreeType && DEGREE_LABEL[t.degreeType]) || '';

function aiRateColor(rate: number, threshold: number): string {
  if (rate <= threshold) return '#10b981';
  if (rate <= threshold * 1.5) return '#f59e0b';
  return '#ef4444';
}

function TaskCard({ task, onPress }: { task: DetectTask; onPress: () => void }) {
  const status = STATUS_LABEL[task.status];
  return (
    <Pressable style={styles.card} onPress={onPress}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle} numberOfLines={1}>{task.paperTitle}</Text>
        <Text style={[styles.status, { color: status.color }]}>{status.text}</Text>
      </View>
      <View style={styles.cardBody}>
        <Text style={styles.meta}>{sceneOf(task)} · 红线 {task.threshold}% · {String(task.createdAt).slice(0, 16)}</Text>
        {task.status === 'DONE' && task.aiRate != null && (
          <Text style={[styles.aiRate, { color: aiRateColor(task.aiRate, task.threshold) }]}>
            AI 率 {task.aiRate.toFixed(1)}%
          </Text>
        )}
      </View>
    </Pressable>
  );
}

export default function TaskListScreen() {
  const router = useRouter();
  const { data, isLoading, refetch } = useQuery({ queryKey: ['tasks'], queryFn: listTasks });

  return (
    <View style={styles.container}>
      <FlatList
        ListHeaderComponent={
          <View style={styles.quick}>
            <Pressable style={[styles.quickItem, styles.quickPrimary]} onPress={() => router.push('/upload')}><Text style={styles.quickIcon}>📤</Text><Text style={[styles.quickText, { color: '#fff' }]}>上传论文</Text></Pressable>
            <Pressable style={styles.quickItem} onPress={() => router.push('/assistant/chat')}><Text style={styles.quickIcon}>💬</Text><Text style={styles.quickText}>问小白</Text></Pressable>
            <Pressable style={styles.quickItem} onPress={() => router.push('/verify')}><Text style={styles.quickIcon}>🛡️</Text><Text style={styles.quickText}>验证报告</Text></Pressable>
          </View>
        }
        data={data ?? []}
        keyExtractor={(t) => String(t.id)}
        renderItem={({ item }) => (
          <TaskCard task={item} onPress={() => router.push(`/task/${item.id}`)} />
        )}
        refreshControl={<RefreshControl refreshing={isLoading} onRefresh={refetch} />}
        contentContainerStyle={{ padding: 16 }}
        ListEmptyComponent={
          !isLoading ? <Text style={styles.empty}>暂无检测记录，去「上传检测」提交论文</Text> : null
        }
      />

      <Pressable style={styles.fab} onPress={() => router.push('/assistant/chat')}>
        <Image source={require('../../assets/xiaobai.gif')} style={styles.fabImg} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f4f6' },
  quick: { flexDirection: 'row', gap: 10, marginBottom: 14 },
  quickItem: { flex: 1, backgroundColor: '#fff', borderRadius: 12, paddingVertical: 12, alignItems: 'center', gap: 4, borderWidth: 1, borderColor: '#e5e7eb' },
  quickPrimary: { backgroundColor: '#0D9488', borderColor: '#0D9488' },
  quickIcon: { fontSize: 18 }, quickText: { fontSize: 12, fontWeight: '600', color: '#111827' },
  card: {
    backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 12,
    shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 1,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardTitle: { fontSize: 15, fontWeight: '600', flex: 1, marginRight: 8, color: '#111827' },
  status: { fontSize: 13, fontWeight: '600' },
  cardBody: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 10, alignItems: 'center' },
  meta: { fontSize: 12, color: '#6b7280' },
  aiRate: { fontSize: 16, fontWeight: '700' },
  empty: { textAlign: 'center', color: '#9ca3af', marginTop: 60 },
  fab: { position: 'absolute', right: 20, bottom: 24, width: 56, height: 56, borderRadius: 28, elevation: 4, shadowColor: '#000', shadowOpacity: 0.15, shadowRadius: 6 },
  fabImg: { width: 56, height: 56, borderRadius: 28 },
});
