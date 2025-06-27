# apis/groups_api.py
import streamlit as st
from utils.fetch import make_api_request
from utils.auth import get_gitlab_headers
from urllib.parse import quote  # noqa: F401
import csv
from apis.users_api import get_user_id
from apis.commits_api import safe_api_request



GITLAB_URL = "https://code.swecha.org"

def get_all_users_from_group(group_id):
    all_members = []
    page = 1
    per_page = 100  # Max GitLab allows
    while True:
        url = f"{GITLAB_URL}/api/v4/groups/{group_id}/members/all?page={page}&per_page={per_page}"
        response = make_api_request(url, get_gitlab_headers())
        if not response:
            break
        all_members.extend(response)
        if len(response) < per_page:
            break  # No more pages
        page += 1
    return all_members

def add_members_to_group(group_id, filename, access_level=30):
    with open(filename, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            username = row["username"].strip()
            user_id = get_user_id(username)
            if not user_id:
                continue
            url = f"{GITLAB_URL}/api/v4/groups/{group_id}/members"
            data = {"user_id": user_id, "access_level": access_level}
            response = make_api_request(url, get_gitlab_headers(), data=data)
            if response:
                print(f"✅ Added '{username}' to the group.")

def update_access_level(group_id, filename, level):
    with open(filename, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            username = row["username"].strip()
            user_id = get_user_id(username)
            if not user_id:
                continue
            url = f"{GITLAB_URL}/api/v4/groups/{group_id}/members/{user_id}"
            data = {"access_level": level}
            response = make_api_request(url, get_gitlab_headers(), data=data)
            if response:
                print(f"🔄 Updated access level for '{username}'")

def run_groups():
    print("\n👥 Manage GitLab Groups")
    group_id= input("📥 Enter Group ID: ").strip()
    print("1. List Members")
    print("2. Add Members from CSV")
    print("3. Update Access Level")
    choice = input("Enter choice: ").strip()

    if choice == "1":
        members = get_all_users_from_group(group_id)
        if members:
            print(f"\n👥 Members in group {group_id}:")
            for member in members:
                print(f"- {member['name']} ({member['username']})")
        else:
            print("❌ No members found.")

    elif choice == "2":
        filename = input("📄 Enter CSV filename: ").strip()
        add_members_to_group(group_id, filename)
    
    elif choice == "3":
        filename = input("📄 Enter CSV filename: ").strip()
        level = int(input("🔒 Enter access level (e.g., 30 for Developer): "))
        update_access_level(group_id, filename, level)

    else:
        print("❌ Invalid choice.")


# @st.cache_data(ttl=300)  # Cache for 5 minutes
def get_group_members(group_id,debug_mode = False):
    """Fetch all members from a GitLab group with improved error handling"""
    headers = get_gitlab_headers()
    if not headers:
        return {"success": False, "error": "No valid GitLab token found"}
    
    if debug_mode:
        st.write(f"🔍 Fetching members for group ID: {group_id}")  
    
    members = []
    page = 1
    per_page = 100
    
    while True:
        url = f"{GITLAB_URL}/api/v4/groups/{group_id}/members/all"
        params = {"page": page, "per_page": per_page}
        
        result = safe_api_request(url, headers, params)
        
        if not result["success"]:
            return result
        
        response = result["data"]
        
        if not isinstance(response, list):
            return {"success": False, "error": f"Unexpected response format. Expected list, got {type(response)}"}
            
        members.extend(response)
        
        if debug_mode:
            st.write(f"📄 Page {page}: Found {len(response)} members")
        
        if len(response) < per_page:
            break
            
        page += 1
        
        # Safety limit
        if page > 50:
            st.warning("⚠️ Hit page limit for members. Some members might not be loaded.")
            break
    
    if debug_mode:
        st.write(f"✅ Total members loaded: {len(members)}")
    
    return {"success": True, "data": members}
