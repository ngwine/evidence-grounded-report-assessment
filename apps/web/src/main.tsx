import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import AuthenticatedApp from './AuthenticatedApp';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {import.meta.env.VITE_APP_MODE === 'authenticated' ? <AuthenticatedApp /> : <App />}
  </React.StrictMode>,
);
