import {
  IconChevronRight,
  IconDots,
  IconHeart,
  IconLogout,
  IconMessage,
  IconPlayerPause,
  IconSettings,
  IconStar,
  IconSwitchHorizontal,
  IconTrash,
} from '@tabler/icons-react';
import { ActionIcon, Avatar, Group, Menu, Text, useMantineTheme } from '@mantine/core';

export function UserMenu() {
  const theme = useMantineTheme();
  return (
    <Group justify="center">
      <Menu
        withArrow
        width={300}
        position="bottom"
        transitionProps={{ transition: 'pop' }}
        withinPortal
      >
        <Menu.Target>
          <ActionIcon variant="default">
            <IconDots size={16} stroke={1.5} />
          </ActionIcon>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Item rightSection={<IconChevronRight size={16} stroke={1.5} />}>
            <Group>
              <Avatar
                radius="xl"
                src="https://raw.githubusercontent.com/mantinedev/mantine/master/.demo/avatars/avatar-7.png"
              />

              <div>
                <Text fw={500}>Nancy Eggshacker</Text>
                <Text size="xs" c="dimmed">
                  neggshaker@mantine.dev
                </Text>
              </div>
            </Group>
          </Menu.Item>

          <Menu.Divider />

          <Menu.Item leftSection={<IconHeart size={16} stroke={1.5} color={theme.colors.red[6]} />}>
            Liked posts
          </Menu.Item>
          <Menu.Item
            leftSection={<IconStar size={16} stroke={1.5} color={theme.colors.yellow[6]} />}
          >
            Saved posts
          </Menu.Item>
          <Menu.Item
            leftSection={<IconMessage size={16} stroke={1.5} color={theme.colors.blue[6]} />}
          >
            Your comments
          </Menu.Item>

          <Menu.Label>Settings</Menu.Label>
          <Menu.Item leftSection={<IconSettings size={16} stroke={1.5} />}>
            Account settings
          </Menu.Item>
          <Menu.Item leftSection={<IconSwitchHorizontal size={16} stroke={1.5} />}>
            Change account
          </Menu.Item>
          <Menu.Item leftSection={<IconLogout size={16} stroke={1.5} />}>Logout</Menu.Item>

          <Menu.Divider />

          <Menu.Label>Danger zone</Menu.Label>
          <Menu.Item leftSection={<IconPlayerPause size={16} stroke={1.5} />}>
            Pause subscription
          </Menu.Item>
          <Menu.Item color="red" leftSection={<IconTrash size={16} stroke={1.5} />}>
            Delete account
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
    </Group>
  );
}
