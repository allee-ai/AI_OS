// Feed Viewers - Native UI for each feed module
export { default as EmailViewer } from './EmailViewer';
export { default as GithubViewer } from './GithubViewer';
export { default as DiscordViewer } from './DiscordViewer';

// Viewer registry - maps feed name to component
import EmailViewer from './EmailViewer';
import GithubViewer from './GithubViewer';
import DiscordViewer from './DiscordViewer';

export const FEED_VIEWERS: Record<string, React.ComponentType> = {
  email: EmailViewer,
  github: GithubViewer,
  discord: DiscordViewer,
};

// Default placeholder for feeds without a custom viewer
export { default as DefaultViewer } from './DefaultViewer';
