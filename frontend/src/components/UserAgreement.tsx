import { useEffect, useRef, useState } from "react";
import { useAgreement } from "../agreement";

export function UserAgreement() {
  const open = useAgreement((s) => s.open);
  const accept = useAgreement((s) => s.accept);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [atEnd, setAtEnd] = useState(false);

  useEffect(() => {
    if (!open) { setAtEnd(false); return; }
    const body = bodyRef.current;
    if (body && body.scrollHeight <= body.clientHeight + 4) setAtEnd(true);
  }, [open]);

  if (!open) return null;

  const onScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const body = e.currentTarget;
    if (body.scrollTop + body.clientHeight >= body.scrollHeight - 16) setAtEnd(true);
  };

  return (
    <div className="modal-overlay open" role="dialog" aria-modal="true" aria-label="User Agreement">
      <div className="modal glass agreement-modal">
        <div className="agr-head">
          <div className="agr-icon"><i className="fa-solid fa-file-signature"></i></div>
          <div>
            <span className="agr-title">User Agreement</span>
            <span className="agr-sub">Please read the terms below. Scroll to the bottom to continue.</span>
          </div>
        </div>

        <div className="agr-body" ref={bodyRef} onScroll={onScroll}>
          <h4>SolRich - Terms of Use</h4>
          <p><b>Copyright © 2026 Finnerich.</b> SolRich (the "Software") is free and open-source software,
            licensed under the <b>Apache License, Version 2.0</b>.</p>

          <h4>1. License</h4>
          <p>SolRich is licensed under the <b>Apache License, Version 2.0</b>. You may use, modify and
            distribute the Software under the terms of that license; a full copy is included with the source
            and available at apache.org/licenses/LICENSE-2.0. Unless required by applicable law or agreed to in
            writing, the Software is provided on an "AS IS" basis, without warranties or conditions of any kind.</p>

          <h4>2. Use at your own risk</h4>
          <p>SolRich automates a third-party game. Automation may violate that game's and/or its platform's
            Terms of Service and can result in warnings, suspensions or permanent bans. You use the Software
            <b> entirely at your own risk</b> and are solely responsible for any consequences to your accounts.</p>

          <h4>3. Your accounts &amp; tokens</h4>
          <p>Linking a Roblox <code>.ROBLOSECURITY</code> login cookie is optional. A login cookie can grant
            access to an account and must be treated like a password. Only link an account you own on a trusted
            device. Linked cookies are stored outside <code>config.json</code> in a separate local file protected
            with <b>Windows DPAPI encryption tied to your current Windows user</b>. SolRich refuses to save new
            cookies if that protection is unavailable.</p>
          <p>Cookies are sent only to official Roblox services when SolRich validates or launches an account;
            they are not sent to the SolRich developer, Discord, webhooks or analytics. Browser login opens the
            official Roblox login page in an isolated temporary browser profile, reads the Roblox cookie after
            sign-in, and removes that profile afterward. SolRich does not read or store your Roblox password.</p>
          <p>Windows encryption protects stored data at rest, but cannot protect an unlocked or infected PC.
            You can delete local login data inside SolRich. If a cookie may have been exposed, you should also
            sign out of Roblox sessions or change your password to revoke it.</p>

          <h4>4. Notifications</h4>
          <p>If you configure Discord webhooks, SolRich posts messages to the webhook URLs you provide. This
            uses Discord's official incoming-webhook feature; no Discord account or user token is used.</p>

          <h4>5. No warranty &amp; liability</h4>
          <p>THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND. The Author is not liable for any
            damages, account actions, data loss or other liability arising from your use of the Software, to the
            maximum extent permitted by law.</p>

          <h4>6. Third-party components</h4>
          <p>SolRich uses open-source components that remain under their own licenses (see THIRD-PARTY-NOTICES).
            This agreement covers SolRich's own software only.</p>

          <p className="agr-final">By clicking "I have read and accept", you confirm you have read, understood
            and agree to these terms. If you do not agree, do not use SolRich.</p>
        </div>

        {!atEnd && (
          <div className="agr-scrollhint"><i className="fa-solid fa-arrow-down"></i> Scroll to the bottom to continue</div>
        )}

        <div className="agr-foot">
          <button className="agr-accept" disabled={!atEnd} onClick={accept}>
            <i className="fa-solid fa-check"></i> I have read and accept
          </button>
        </div>
      </div>
    </div>
  );
}
