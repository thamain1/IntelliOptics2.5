import { PublicClientApplication, AuthenticationResult } from '@azure/msal-browser';

// MSAL configuration.  These values should match your Azure AD app
// registration.  They are injected via environment variables at
// build-time using Vite's import.meta.env mechanism.  See README for
// details on configuring Azure AD authentication.

const clientId = (import.meta.env.VITE_AZURE_CLIENT_ID as string) || "placeholder-client-id";
const tenantId = (import.meta.env.VITE_AZURE_TENANT_ID as string) || "common";

// Check if MSAL is properly configured BEFORE creating the instance
export const isMsalConfigured =
    clientId !== "YOUR_CLIENT_ID_HERE" &&
    clientId !== "placeholder-client-id" &&
    clientId !== "DISABLED" &&
    tenantId !== "YOUR_TENANT_ID_HERE" &&
    tenantId !== "your_tenant_id_here" &&
    tenantId !== "DISABLED" &&
    tenantId !== "common";

const msalConfig = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: 'http://localhost:3000',
  },
  cache: {
    cacheLocation: 'localStorage',
    storeAuthStateInCookie: false,
  },
};

// Only create MSAL instance if properly configured
export const msalInstance: PublicClientApplication | null = isMsalConfigured
    ? new PublicClientApplication(msalConfig)
    : null;

// Initialize MSAL instance (required for msal-browser v2+)
if (isMsalConfigured && msalInstance) {
    msalInstance.initialize().then(() => {
        // Optional: handle redirects if you were to use loginRedirect
        // msalInstance.handleRedirectPromise().catch(console.error);
    }).catch(console.error);
} else {
    console.info("MSAL disabled: Using local JWT authentication instead.");
}


export async function login(): Promise<AuthenticationResult | null> {
  if (!isMsalConfigured || !msalInstance) {
    console.info("MSAL not configured. Use local login instead.");
    return null;
  }

  try {
    return await msalInstance.loginPopup({ scopes: ['openid', 'profile', 'email'] });
  } catch (error: any) {
    if (error.errorCode === 'interaction_in_progress') {
        console.warn("Interaction in progress. Attempting to recover...");
        alert("Authentication is already in progress in another window or tab. Please complete it there, or refresh this page.");
        return null;
    }
    console.error("Login failed:", error);
    throw error;
  }
}

export function logout(): void {
  if (isMsalConfigured && msalInstance) {
    msalInstance.logoutPopup();
  }
  // Always clear local storage
  localStorage.removeItem('local_access_token');
}