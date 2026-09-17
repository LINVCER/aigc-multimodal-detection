import { Tabs } from 'expo-router';
import { Text } from 'react-native';

function TabIcon({ label, focused }: { label: string; focused: boolean }) {
  return <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.4 }}>{label}</Text>;
}

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ headerTitleAlign: 'center', tabBarActiveTintColor: '#1a56db' }}>
      <Tabs.Screen
        name="index"
        options={{
          title: '检测记录',
          tabBarIcon: ({ focused }) => <TabIcon label="📋" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="upload"
        options={{
          title: '上传检测',
          tabBarIcon: ({ focused }) => <TabIcon label="📤" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: '我的',
          tabBarIcon: ({ focused }) => <TabIcon label="👤" focused={focused} />,
        }}
      />
    </Tabs>
  );
}
