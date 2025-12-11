import os
import secrets
import time
from typing import cast
from urllib.parse import urlencode

import requests
import streamlit as st

from gateway_client import delete_profile, ingest_and_rewrite, ingest_memories
from llm import chat, set_model
from model_config import MODEL_CHOICES, MODEL_TO_PROVIDER, MODEL_DISPLAY_NAMES



def _generate_session_name(base: str = "Session") -> str:
    existing = set(st.session_state.get("session_order", []))
    idx = 1
    while True:
        candidate = f"{base} {idx}"
        if candidate not in existing:
            return candidate
        idx += 1

def ensure_session_state() -> None:
    if "sessions" not in st.session_state:
        st.session_state.sessions = {}
    if "session_order" not in st.session_state:
        st.session_state.session_order = []
    if (
        "active_session_id" not in st.session_state
        or st.session_state.active_session_id not in st.session_state.sessions
    ):
        default_name = _generate_session_name()
        st.session_state.sessions.setdefault(default_name, {"history": []})
        if default_name not in st.session_state.session_order:
            st.session_state.session_order.append(default_name)
        st.session_state.active_session_id = default_name
    if "session_select" not in st.session_state:
        st.session_state.session_select = st.session_state.active_session_id
    if st.session_state.session_select not in st.session_state.sessions:
        st.session_state.session_select = st.session_state.active_session_id
    st.session_state.setdefault(
        "rename_session_name", st.session_state.active_session_id
    )
    st.session_state.setdefault(
        "rename_session_synced_to", st.session_state.active_session_id
    )
    st.session_state.history = cast(
        list[dict],
        st.session_state.sessions[
            st.session_state.active_session_id
        ].setdefault("history", []),
    )


def create_session(session_name: str | None = None) -> tuple[bool, str]:
    ensure_session_state()
    candidate = (session_name or "").strip()
    if not candidate:
        candidate = _generate_session_name()
    if candidate in st.session_state.sessions:
        return False, candidate
    st.session_state.sessions[candidate] = {"history": []}
    st.session_state.session_order.append(candidate)
    st.session_state.active_session_id = candidate
    st.session_state.session_select = candidate
    st.session_state.history = cast(
        list[dict], st.session_state.sessions[candidate]["history"]
    )
    st.session_state.rename_session_name = candidate
    st.session_state.rename_session_synced_to = candidate
    return True, candidate


def rename_session(current_name: str, new_name: str) -> bool:
    ensure_session_state()
    target = new_name.strip()
    if not target or target == current_name:
        return False
    if target in st.session_state.sessions:
        return False
    st.session_state.sessions[target] = st.session_state.sessions.pop(current_name)
    order = st.session_state.session_order
    order[order.index(current_name)] = target
    if st.session_state.active_session_id == current_name:
        st.session_state.active_session_id = target
        st.session_state.session_select = target
    st.session_state.history = cast(
        list[dict],
        st.session_state.sessions[st.session_state.active_session_id]["history"],
    )
    st.session_state.rename_session_name = target
    st.session_state.rename_session_synced_to = target
    return True


def delete_session(session_name: str) -> bool:
    ensure_session_state()
    if session_name not in st.session_state.sessions:
        return False
    if len(st.session_state.session_order) <= 1:
        return False
    st.session_state.sessions.pop(session_name, None)
    st.session_state.session_order.remove(session_name)
    if st.session_state.active_session_id == session_name:
        st.session_state.active_session_id = st.session_state.session_order[-1]
        st.session_state.session_select = st.session_state.active_session_id
        st.session_state.rename_session_name = st.session_state.active_session_id
        st.session_state.rename_session_synced_to = st.session_state.active_session_id
    st.session_state.history = cast(
        list[dict],
        st.session_state.sessions[st.session_state.active_session_id]["history"],
    )
    return True


def rewrite_message(
    msg: str, persona_name: str, show_rationale: bool, use_memory: bool = True
) -> str:
    # If memory is disabled or Control persona, don't use memory
    if not use_memory or persona_name.lower() == "control":
        rewritten_msg = msg
        if show_rationale:
            rewritten_msg += " At the beginning of your response, please say the following in ITALIC: 'Persona Rationale: No personalization applied.'. Begin your answer on the next line."
        return rewritten_msg
    
    try:
        rewritten_msg = ingest_and_rewrite(
            user_id=persona_name, query=msg
        )
        if show_rationale:
            rewritten_msg += " At the beginning of your response, please say the following in ITALIC: 'Persona Rationale: ' followed by 1 sentence about how your reasoning for how the persona traits influenced this response, also in italics. Begin your answer on the next line."
    except Exception as e:
        st.error(f"Failed to ingest_and_append message: {e}")
        raise
    print(rewritten_msg)
    return rewritten_msg

# ──────────────────────────────────────────────────────────────
# Page setup & CSS
# ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="MemMachine Chatbot", layout="wide")

try:
    with open("./styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass
    
ensure_session_state()


HEADER_STYLE = """
<style>
.memmachine-header-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 1.2rem;
}
.memmachine-header-links {
    display: inline-flex;
    gap: 14px;
    align-items: center;
    background: transparent;
    padding: 0;
    border-radius: 0;
}
.memmachine-header-links .powered-by {
    color: #667eea;
    font-weight: 700;
    font-size: 16px;
    margin-right: 6px;
    white-space: nowrap;
}
.memmachine-header-links a {
    text-decoration: none;
    color: inherit;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border-radius: 0;
    transition: opacity 0.2s ease;
}
.memmachine-header-links a:hover {
    opacity: 0.7;
}
.memmachine-header-links img,
.memmachine-header-links svg {
    width: 22px;
    height: 22px;
}
@media (max-width: 768px) {
    .memmachine-header-wrapper {
        justify-content: center;
        margin-bottom: 0.8rem;
    }
    .memmachine-header-links {
        flex-wrap: wrap;
        row-gap: 8px;
        justify-content: center;
    }
}
</style>
"""

HEADER_HTML = """
<div class="memmachine-header-wrapper">
  <div class="memmachine-header-links">
    <span class="powered-by">Powered by MemMachine</span>
    <a href="https://memmachine.ai/" target="_blank" title="MemMachine">
      <img src="https://avatars.githubusercontent.com/u/226739620?s=48&v=4" alt="MemMachine logo"/>
    </a>
    <a href="https://github.com/MemMachine/MemMachine" target="_blank" title="GitHub Repository">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
      </svg>
    </a>
    <a href="https://discord.gg/usydANvKqD" target="_blank" title="Discord Community">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
        <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
      </svg>
    </a>
  </div>
</div>
"""

st.markdown(HEADER_STYLE, unsafe_allow_html=True)
st.markdown(HEADER_HTML, unsafe_allow_html=True)



# ──────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────
default_model = MODEL_CHOICES[0] if MODEL_CHOICES else "gpt-4.1-mini"
model_id = default_model
provider = MODEL_TO_PROVIDER.get(default_model, "openai")
selected_persona = "Charlie"
persona_name = "Charlie"
skip_rewrite = False
compare_personas = False
show_rationale = False

with st.sidebar:
    st.markdown("#### Sessions")
    session_options = st.session_state.session_order
    active_session = st.session_state.active_session_id
    if st.session_state.rename_session_synced_to != active_session:
        st.session_state.rename_session_name = active_session
        st.session_state.rename_session_synced_to = active_session

    for idx, session_name in enumerate(session_options, start=1):
        is_active = session_name == active_session
        button_label = f"{session_name}"
        row = st.container()
        with row:
            button_col, menu_col = st.columns([0.8, 0.2])
            with button_col:
                if st.button(
                    button_label,
                    key=f"session_button_{session_name}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    if not is_active:
                        st.session_state.active_session_id = session_name
                        st.session_state.session_select = session_name
                        st.session_state.history = cast(
                            list[dict],
                            st.session_state.sessions[session_name]["history"],
                        )
                        st.session_state.rename_session_name = session_name
                        st.session_state.rename_session_synced_to = session_name
                        st.rerun()
            with menu_col:
                if hasattr(st, "popover"):
                    menu_container = st.popover("⋯", use_container_width=True)
                else:
                    menu_container = st.expander(
                        "⋯", expanded=False, key=f"session_actions_{session_name}"
                    )
                with menu_container:
                    st.markdown(f"**Actions for {session_name}**")
                    rename_value = st.text_input(
                        "Rename session",
                        value=session_name,
                        key=f"rename_session_input_{session_name}",
                    )
                    if st.button(
                        "Rename",
                        use_container_width=True,
                        key=f"rename_session_button_{session_name}",
                    ):
                        rename_target = rename_value.strip()
                        if not rename_target:
                            st.warning("Enter a session name to rename.")
                        elif rename_target == session_name:
                            st.info("Session name unchanged.")
                        elif rename_target in st.session_state.sessions:
                            st.warning(f"Session '{rename_target}' already exists.")
                        elif rename_session(session_name, rename_target):
                            st.success(f"Session renamed to '{rename_target}'.")
                            st.rerun()
                        else:
                            st.error("Unable to rename session. Please try again.")

                    st.divider()
                    if st.button(
                        "Delete session",
                        use_container_width=True,
                        type="secondary",
                        key=f"delete_session_button_{session_name}",
                    ):
                        if delete_session(session_name):
                            new_active = st.session_state.active_session_id
                            st.session_state.session_select = new_active
                            st.session_state.rename_session_name = new_active
                            st.session_state.rename_session_synced_to = new_active
                            st.success(f"Session '{session_name}' deleted.")
                            st.rerun()
                        else:
                            st.warning("Cannot delete the last remaining session.")

    with st.form("create_session_form", clear_on_submit=True):
        new_session_name = st.text_input(
            "New session name",
            key="create_session_name",
            placeholder="Leave blank for automatic name",
        )
        if st.form_submit_button("Create session", use_container_width=True):
            success, created_name = create_session(new_session_name)
            if success:
                st.success(f"Session '{created_name}' created.")
                st.rerun()
            else:
                st.warning(f"Session '{created_name}' already exists.")

    st.divider()

    st.markdown("#### Choose Model")

    # Create display options with categories
    display_options = [MODEL_DISPLAY_NAMES[model] for model in MODEL_CHOICES]
    
    selected_display = st.selectbox(
        "Choose Model", display_options, index=0, label_visibility="collapsed"
    )
    
    # Get the actual model ID from the display name
    model_id = next(model for model, display in MODEL_DISPLAY_NAMES.items() 
                   if display == selected_display)
    
    provider = MODEL_TO_PROVIDER[model_id]
    set_model(model_id)

    st.markdown("#### User Identity")
    
    # Get Hugging Face user ID if available (in HF Spaces)
    hf_user_id = os.getenv("SPACE_USER") or os.getenv("HF_USERNAME") or os.getenv("HF_USER")
    
    # Check if we're on Hugging Face Spaces (not local)
    is_hf_space = os.getenv("SPACE_ID") is not None or os.getenv("HF_ENDPOINT") is not None
    
    def validate_hf_token(token: str) -> tuple[bool, str, str]:
        """Validate HF token and return (is_valid, username, error_message)."""
        token = token.strip()
        if not token:
            return False, "", "Token cannot be empty"
        
        # Remove any whitespace or newlines that might have been copied
        token = "".join(token.split())
        
        # Try using huggingface_hub library if available, otherwise fall back to API
        try:
            from huggingface_hub import whoami
            try:
                user_info = whoami(token=token)
                username = user_info.get("name") or user_info.get("username") or ""
                if username:
                    return True, username, ""
                else:
                    return False, "", "Token validated but username not found in response."
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "Unauthorized" in error_msg or "Invalid" in error_msg:
                    return False, "", f"Invalid token. Please verify your token is correct and has Read permissions. Error: {error_msg[:100]}"
                return False, "", f"Validation error: {error_msg[:150]}"
        except ImportError:
            # Fall back to direct API call if huggingface_hub not available
            pass
        
        # Fallback: Use the HF whoami endpoint directly
        endpoint = "https://huggingface.co/api/whoami"
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "MemMachine-Playground/1.0"
        }
        
        try:
            resp = requests.get(endpoint, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                user_data = resp.json()
                # Try different possible username fields
                username = (
                    user_data.get("name") or 
                    user_data.get("username") or 
                    user_data.get("user") or
                    ""
                )
                if username:
                    return True, username, ""
                else:
                    return False, "", f"Token validated but username not found. Response: {str(user_data)[:100]}"
            elif resp.status_code == 401:
                error_detail = ""
                try:
                    error_data = resp.json()
                    error_detail = error_data.get("error", "")
                except:
                    pass
                return False, "", f"Invalid token (401). The token may be expired, revoked, or incorrect. {error_detail} Please create a new Read token at https://huggingface.co/settings/tokens"
            elif resp.status_code == 403:
                return False, "", f"Token access denied (403). Please ensure your token has Read permissions."
            else:
                error_text = ""
                try:
                    error_data = resp.json()
                    error_text = error_data.get("error", resp.text[:100])
                except:
                    error_text = resp.text[:100] if hasattr(resp, 'text') else f"Status {resp.status_code}"
                return False, "", f"Authentication failed (Status {resp.status_code}): {error_text}"
                
        except requests.exceptions.Timeout:
            return False, "", "Request timed out. Please check your internet connection and try again."
        except requests.exceptions.RequestException as e:
            return False, "", f"Network error: {str(e)}. Please try again."
        except Exception as e:
            return False, "", f"Validation error: {str(e)}. Please try again."
    
    if is_hf_space:
        # On HF Spaces - require token authentication for security
        if "hf_authenticated_user" not in st.session_state:
            st.warning("🔐 **Authentication Required**")
            st.caption("To protect your memories, please authenticate with your Hugging Face account.")
            
            token_input = st.text_input(
                "Enter your Hugging Face Access Token",
                key="hf_token_input",
                type="password",
                placeholder="hf_xxxxxxxxxxxxxxxxxxxxx",
                help="❓ Create a Read token: https://huggingface.co/settings/tokens"
            )
            
            if st.button("Authenticate", use_container_width=True, type="primary"):
                if token_input.strip():
                    with st.spinner("Validating token..."):
                        is_valid, username, error_msg = validate_hf_token(token_input.strip())
                    if is_valid and username:
                        st.session_state.hf_authenticated_user = username
                        st.session_state.hf_token = token_input.strip()  # Store for future use
                        # Use custom purple styling instead of green success message
                        st.markdown(f"""
                        <div style="
                            background-color: rgba(102, 126, 234, 0.1);
                            border-left: 4px solid #667eea;
                            padding: 0.75rem 1rem;
                            border-radius: 0.25rem;
                            margin-bottom: 0.5rem;
                        ">
                            <div style="color: #667eea; font-weight: 500;">
                                ✅ Authenticated as <strong>{username}</strong>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        st.rerun()
                    else:
                        error_display = error_msg if error_msg else "Invalid token. Please check your Hugging Face access token."
                        st.error(f"❌ {error_display}")
                else:
                    st.error("Please enter your access token")
            st.info("💡 **Privacy Note:** Your token is used only for authentication. It is not stored or shared anywhere.")
            st.stop()
        else:
            # User is authenticated - lock to their username
            persona_name = st.session_state.hf_authenticated_user
            # Use custom purple styling instead of green success message
            st.markdown(f"""
            <div style="
                background-color: rgba(102, 126, 234, 0.1);
                border-left: 4px solid #667eea;
                padding: 0.75rem 1rem;
                border-radius: 0.25rem;
                margin-bottom: 0.5rem;
            ">
                <div style="color: #667eea; font-weight: 500;">
                    🔐 Authenticated as: <strong>{persona_name}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Your memories are secured to your account only.")
            if st.button("🔓 Sign Out", use_container_width=True):
                del st.session_state.hf_authenticated_user
                if "hf_token" in st.session_state:
                    del st.session_state.hf_token
                st.rerun()
    elif hf_user_id:
        # HF user ID detected automatically
        persona_name = hf_user_id
        st.info(f"👤 Signed in as: **{hf_user_id}**")
        st.caption("Your memories are personalized to your account.")
    else:
        # Local/testing mode - allow persona selection
        selected_persona = st.selectbox(
            "Choose user persona",
            ["Charlie", "Jing", "Charles", "Control"],
            label_visibility="collapsed",
        )
        custom_persona = st.text_input("Or enter your name", "")
        persona_name = (
            custom_persona.strip() if custom_persona.strip() else selected_persona
        )

    # Memory toggle - default enabled
    if "memmachine_enabled" not in st.session_state:
        st.session_state.memmachine_enabled = True
    if "compare_personas" not in st.session_state:
        st.session_state.compare_personas = True
    
    memmachine_enabled = st.checkbox(
        "Enable MemMachine",
        value=st.session_state.memmachine_enabled,
        help="Enable MemMachine's persistent memory system. When unchecked, the AI will respond without memory (Control Persona mode)."
    )
    st.session_state.memmachine_enabled = memmachine_enabled
    
    if memmachine_enabled:
        # Enhanced "Compare with control persona" section with cool styling
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 0.5rem 0;
            border: 2px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        ">
            <div style="display: flex; align-items: center; gap: 0.5rem; color: white;">
                <span style="font-size: 1.5rem;">⚖️</span>
                <div>
                    <div style="font-weight: 600; font-size: 1rem;">Side-by-Side Comparison with Control Persona</div>
                    <div style="font-size: 0.85rem; opacity: 0.9;">Compare MemMachine responses vs Control Persona (no memory)</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        compare_personas = st.checkbox(
            "🔄 Compare with control persona",
            value=st.session_state.compare_personas,
            help="Enable side-by-side comparison to see how MemMachine's persistent memory enhances responses compared to the control persona (no memory)"
        )
        st.session_state.compare_personas = compare_personas
    else:
        compare_personas = False
    show_rationale = st.checkbox("Show Persona Rationale")

    st.divider()
    if st.button("Clear chat", use_container_width=True):
        active = st.session_state.active_session_id
        st.session_state.sessions[active]["history"].clear()
        st.session_state.history = cast(
            list[dict],
            st.session_state.sessions[active]["history"],
        )
        st.rerun()
    if st.button("Delete Profile", use_container_width=True):
        success = delete_profile(persona_name)
        active = st.session_state.active_session_id
        st.session_state.sessions[active]["history"].clear()
        st.session_state.history = cast(
            list[dict],
            st.session_state.sessions[active]["history"],
        )
        if success:
            st.success(f"Profile for '{persona_name}' deleted.")
        else:
            st.error(f"Failed to delete profile for '{persona_name}'.")
    st.divider()



# ──────────────────────────────────────────────────────────────
# Enforce alternating roles
# ──────────────────────────────────────────────────────────────
def clean_history(history: list[dict], persona: str) -> list[dict]:
    out = []
    for turn in history:
        if turn.get("role") == "user":
            out.append({"role": "user", "content": turn["content"]})
        elif turn.get("role") == "assistant" and turn.get("persona") == persona:
            out.append({"role": "assistant", "content": turn["content"]})
    cleaned = []
    last_role = None
    for msg in out:
        if msg["role"] != last_role:
            cleaned.append(msg)
            last_role = msg["role"]
    return cleaned


def append_user_turn(msgs: list[dict], new_user_msg: str) -> list[dict]:
    if msgs and msgs[-1]["role"] == "user":
        msgs[-1] = {"role": "user", "content": new_user_msg}
    else:
        msgs.append({"role": "user", "content": new_user_msg})
    return msgs


def typewriter_effect(text: str, speed: float = 0.02):
    """Generator that yields text word by word to create a typing effect."""
    words = text.split(" ")
    for i, word in enumerate(words):
        if i == 0:
            yield word
        else:
            yield " " + word
        time.sleep(speed)

# ──────────────────────────────────────────────────────────────
# Load Previous Memories Section (Import External Memories)
# ──────────────────────────────────────────────────────────────
if "memories_preview" not in st.session_state:
    st.session_state.memories_preview = None
if "imported_memories_text" not in st.session_state:
    st.session_state.imported_memories_text = ""

# Add expandable section for importing memories
with st.expander("📋 Load Previous Memories (Import from ChatGPT, etc.)", expanded=False):
    st.markdown("**Paste your conversation history or memories from external sources (e.g., ChatGPT, other AI chats)**")
    
    # Text area for pasting memories
    imported_text = st.text_area(
        "Paste your memories/conversations here",
        value=st.session_state.imported_memories_text,
        height=200,
        placeholder="Example:\nUser: What is machine learning?\nAssistant: Machine learning is...\n\nUser: Can you explain neural networks?\nAssistant: Neural networks are...",
        help="Paste any conversation history, notes, or context you want the AI to remember. These will be ingested into MemMachine's memory system and available for future conversations.",
        key="import_memories_textarea"
    )
    
    # File upload option
    uploaded_file = st.file_uploader(
        "Or upload a text file",
        type=['txt', 'md', 'json'],
        help="Upload a text file containing your conversation history or memories"
    )
    
    if uploaded_file is not None:
        try:
            # Read file content
            if uploaded_file.type == "application/json":
                import json
                file_content = json.loads(uploaded_file.read().decode("utf-8"))
                imported_text = str(file_content)
            else:
                imported_text = uploaded_file.read().decode("utf-8")
            st.session_state.imported_memories_text = imported_text
            st.success("File loaded successfully!")
        except Exception as e:
            st.error(f"Error reading file: {e}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("👁️ Preview", use_container_width=True, key="preview_memories"):
            if imported_text and imported_text.strip():
                st.session_state.memories_preview = imported_text
                st.session_state.imported_memories_text = imported_text
                st.rerun()
            else:
                st.warning("Please paste or upload some memories first.")
    
    with col2:
        if st.button("💉 Ingest into MemMachine", use_container_width=True, key="inject_memories_direct"):
            if imported_text and imported_text.strip():
                if persona_name and persona_name != "Control":
                    with st.spinner("Ingesting memories into MemMachine..."):
                        success = ingest_memories(persona_name, imported_text)
                        if success:
                            st.session_state.imported_memories_text = imported_text
                            st.success("✅ Memories successfully ingested into MemMachine! They are now part of your memory system.")
                        else:
                            st.error("❌ Failed to ingest memories. Please try again.")
                else:
                    st.warning("Please authenticate or select a persona to ingest memories.")
                st.rerun()
            else:
                st.warning("Please paste or upload some memories first.")

# Show preview if memories are loaded
if st.session_state.memories_preview:
    with st.expander("📋 Preview Imported Memories", expanded=True):
        memories = st.session_state.memories_preview
        preview_text = str(memories)[:2000]  # Show first 2000 chars
        
        if preview_text:
            st.text_area("Memories Preview", preview_text, height=200, disabled=True, key="memories_preview_text")
            st.caption(f"Total length: {len(str(memories))} characters")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💉 Ingest into MemMachine", use_container_width=True, key="inject_memories_from_preview"):
                    if persona_name and persona_name != "Control":
                        with st.spinner("Ingesting memories into MemMachine..."):
                            success = ingest_memories(persona_name, str(st.session_state.memories_preview))
                            if success:
                                st.success("✅ Memories successfully ingested into MemMachine! They are now part of your memory system.")
                            else:
                                st.error("❌ Failed to ingest memories. Please try again.")
                    else:
                        st.warning("Please authenticate or select a persona to ingest memories.")
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear", use_container_width=True, key="clear_memories_preview"):
                    st.session_state.memories_preview = None
                    st.session_state.imported_memories_text = ""
                    st.rerun()
        else:
            st.info("No memories to preview.")
            st.session_state.memories_preview = None

msg = st.chat_input("Type your message…")
if msg:
    st.session_state.history.append({"role": "user", "content": msg})
    memmachine_enabled = st.session_state.get("memmachine_enabled", True)
    
    if compare_personas and memmachine_enabled:
        all_answers = {}
        rewritten_msg = rewrite_message(msg, persona_name, show_rationale, use_memory=True)
        msgs = clean_history(st.session_state.history, persona_name)
        msgs = append_user_turn(msgs, rewritten_msg)
        try:
            txt, lat, tok, tps = chat(msgs, persona_name)
            all_answers[persona_name] = txt
        except ValueError as e:
            st.error(f"❌ {str(e)}")
            st.stop()

        rewritten_msg_control = rewrite_message(msg, "Control", show_rationale, use_memory=False)
        msgs_control = clean_history(st.session_state.history, "Control")
        msgs_control = append_user_turn(msgs_control, rewritten_msg_control)
        try:
            txt_control, lat, tok, tps = chat(msgs_control, "Arnold")
            all_answers["Control"] = txt_control
        except ValueError as e:
            st.error(f"❌ {str(e)}")
            st.stop()

        st.session_state.history.append(
            {"role": "assistant_all", "axis": "role", "content": all_answers, "is_new": True}
        )
    else:
        # Use memory only if memmachine_enabled is True
        rewritten_msg = rewrite_message(msg, persona_name, show_rationale, use_memory=memmachine_enabled)
        msgs = clean_history(st.session_state.history, persona_name)
        msgs = append_user_turn(msgs, rewritten_msg)
        try:
            txt, lat, tok, tps = chat(
                msgs, "Arnold" if persona_name == "Control" or not memmachine_enabled else persona_name
            )
            st.session_state.history.append(
                {"role": "assistant", "persona": persona_name, "content": txt, "is_new": True}
            )
        except ValueError as e:
            st.error(f"❌ {str(e)}")
            st.stop()
    st.rerun()


# ──────────────────────────────────────────────────────────────
# Memory Status Indicator
# ──────────────────────────────────────────────────────────────
memmachine_enabled = st.session_state.get("memmachine_enabled", True)
status_emoji = "🧠" if memmachine_enabled else "⚪"
status_text = "MemMachine Active" if memmachine_enabled else "No Memory Mode"

# Add status indicator at the top of chat area
status_html = f"""
<div style="display: flex; justify-content: flex-end; margin-bottom: 1rem; padding: 0.5rem 1rem; background: #f0f2f6; border-radius: 0.5rem; border: 1px solid #e0e0e0;">
    <span style="font-size: 0.9rem; color: #666;">
        {status_emoji} <strong>{status_text}</strong>
    </span>
</div>
"""
st.markdown(status_html, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# Chat history display
# ──────────────────────────────────────────────────────────────
for turn in st.session_state.history:
    if turn.get("role") == "user":
        st.chat_message("user").write(turn["content"])
    elif turn.get("role") == "assistant":
        with st.chat_message("assistant"):
            # Use typing effect for new messages, normal display for old ones
            if turn.get("is_new", False):
                st.write_stream(typewriter_effect(turn["content"]))
                # Mark as no longer new so it displays normally on rerun
                turn["is_new"] = False
            else:
                st.write(turn["content"])
    elif turn.get("role") == "assistant_all":
        content_items = list(turn["content"].items())
        is_new = turn.get("is_new", False)
        if len(content_items) >= 2:
            # Enhanced comparison header
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 0.75rem 1rem;
                border-radius: 0.5rem 0.5rem 0 0;
                margin-bottom: 0.5rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
                color: white;
                font-weight: 600;
            ">
                <span style="font-size: 1.2rem;">⚖️</span>
                <span>Side-by-Side Comparison</span>
            </div>
            """, unsafe_allow_html=True)
            
            cols = st.columns([1, 0.03, 1])
            persona_label, persona_response = content_items[0]
            control_label, control_response = content_items[1]
            with cols[0]:
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
                    padding: 1rem;
                    border-radius: 0.5rem;
                    border-left: 4px solid #667eea;
                    margin-bottom: 1rem;
                ">
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        <span style="font-size: 1.2rem;">🧠</span>
                        <strong style="color: #667eea;">{persona_label}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if is_new:
                    st.write_stream(typewriter_effect(persona_response))
                else:
                    st.markdown(
                        f'<div class="answer">{persona_response}</div>',
                        unsafe_allow_html=True,
                    )
            with cols[1]:
                st.markdown(
                    '<div class="vertical-divider"></div>', unsafe_allow_html=True
                )
            with cols[2]:
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, rgba(200, 200, 200, 0.1) 0%, rgba(150, 150, 150, 0.1) 100%);
                    padding: 1rem;
                    border-radius: 0.5rem;
                    border-left: 4px solid #888;
                    margin-bottom: 1rem;
                ">
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        <span style="font-size: 1.2rem;">⚪</span>
                        <strong style="color: #666;">{control_label}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if is_new:
                    st.write_stream(typewriter_effect(control_response))
                else:
                    st.markdown(
                        f'<div class="answer">{control_response}</div>',
                        unsafe_allow_html=True,
                    )
        else:
            for label, response in content_items:
                st.markdown(f"**{label}**")
                if is_new:
                    st.write_stream(typewriter_effect(response))
                else:
                    st.markdown(
                        f'<div class="answer">{response}</div>', unsafe_allow_html=True
                    )
        # Mark as no longer new
        if is_new:
            turn["is_new"] = False