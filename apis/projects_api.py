# from turtle import st
import streamlit as st
from urllib.parse import quote
from utils.fetch import make_api_request
import os
from utils.fetch import fetch_paginated_data
from utils.auth import get_gitlab_headers
from apis.commits_api import safe_api_request, get_gitlab_headers  # noqa: F811
from dateutil.parser import parse as parse_datetime
from collections import defaultdict
GITLAB_API_URL = "https://code.swecha.org/api/v4"
GITLAB_URL = "https://code.swecha.org"

# apis/projects_api.py



# GITLAB_API_URL = "https://code.swecha.org/api/v4"

def get_projects(group_id_or_path):
    url = f"{GITLAB_API_URL}/groups/{group_id_or_path}/projects"
    headers = get_gitlab_headers()
    return fetch_paginated_data(url, headers)


def get_project_id(project_path):
    encoded_path = quote(project_path, safe="")
    url = f"{GITLAB_API_URL}/projects/{encoded_path}"
    headers = {"PRIVATE-TOKEN": os.getenv("GITLAB_TOKEN")}
    response = make_api_request(url, headers)
    if response and "id" in response:
        return response["id"]
    return None

def check_file_in_project(project_path, file_path):
    project_path = project_path.strip()
    file_path = file_path.strip()
    encoded_file = quote(file_path, safe="")

    project_id = get_project_id(project_path)
    if not project_id:
        print(f"❌ Project '{project_path}' not found.")
        return False

    url = f"{GITLAB_API_URL}/projects/{project_id}/repository/files/{encoded_file}/raw"
    headers = {"PRIVATE-TOKEN": os.getenv("GITLAB_TOKEN")}
    response = make_api_request(url, headers, params={"ref": "main"}, return_raw=True)

    return response is not None

def run_check_file():
    print("\n📁 Check File in Project Repository")
    project_path = input("📥 Enter Project Path (e.g., group/project): ").strip()
    file_path = input("📄 Enter File Path (e.g., README.md): ").strip()

    exists = check_file_in_project(project_path, file_path)
    if exists:
        print(f"✅ File '{file_path}' exists in '{project_path}'.")
    else:
        print(f"❌ File '{file_path}' NOT FOUND in '{project_path}'.")

def get_all_accessible_projects(debug_mode=False):
    """Get all accessible projects for the user with improved error handling"""
    headers = get_gitlab_headers()
    if not headers:
        return {"success": False, "error": "No valid GitLab token found"}
    
    projects = []
    page = 1
    per_page = 100
    
    while True:
        url = f"{GITLAB_URL}/api/v4/projects"
        params = {
            "membership": "true",
            "simple": "true", 
            "per_page": per_page,
            "page": page,
            "order_by": "last_activity_at",
            "sort": "desc"
        }
        
        result = safe_api_request(url, headers, params)
        
        if not result["success"]:
            return result
            
        response = result["data"]
        projects.extend(response)
        
        if debug_mode:
            # st.write(f"📄 Projects page {page}: Found {len(response)} projects")
            print(f"📄 Projects page {page}: Found {len(response)} projects")

        if len(response) < per_page:
            break
            
        page += 1
        
        # Safety limit for projects
        if page > 100:
            # st.warning("⚠️ Hit page limit for projects. Some projects might not be loaded.")
            print("⚠️ Hit page limit for projects. Some projects might not be loaded.")
            break
    
    return {"success": True, "data": projects}



def get_project_activity(project_id, project_name, since_date, valid_names,debug_mode=False):
    """Get all activity for a specific project"""
    stats = defaultdict(lambda: {
    "commits": 0,
    "merge_requests": 0,
    "issues": 0,
    
    "push_events": 0,
    "project_names": set(),
    "last_activity": None
})



    headers = get_gitlab_headers()
    if not headers:
        return stats

    try:
    # Get commits from ALL branches
        commits_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/commits"   
        commits_params = {
        "since": since_date.isoformat(), 
        "per_page": 100,
        "all": "true"  # This ensures we get commits from all branches
    }
    
    # Handle pagination for commits
        page = 1
        while True:
            commits_params["page"] = page
            commits_result = safe_api_request(commits_url, headers, commits_params)
        
            if not commits_result["success"]:
                break
            
            commits = commits_result["data"]
            if not commits:  # No more data
                break
            
            for commit in commits:
                author = commit.get("author_name", "Unknown")
                if author in valid_names:
                    stats[author]["commits"] += 1
                    stats[author]["project_names"].add(project_name)
                
                created_at = commit.get("created_at")
                if created_at:
                    try:
                        dt = parse_datetime(created_at)
                        if not stats[author]["last_activity"] or dt > stats[author]["last_activity"]:
                            stats[author]["last_activity"] = dt
                    except Exception:
                        pass
        
        # Check if we've reached the last page
            if len(commits) < 100:  # Less than per_page means last page
                break
            page += 1
    
    # Get merge requests with pagination
        mrs_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/merge_requests"
        mrs_params = {
        "updated_after": since_date.isoformat(), 
        "per_page": 100, 
        "state": "all"
    }
    
        page = 1
        while True:
            mrs_params["page"] = page
            mrs_result = safe_api_request(mrs_url, headers, mrs_params)
        
            if not mrs_result["success"]:
                break
            
            mrs = mrs_result["data"]
            if not mrs:  # No more data
                break
            
            for mr in mrs:
                author_info = mr.get("author", {})
                author = author_info.get("name", "Unknown")
                if author in valid_names:
                    stats[author]["merge_requests"] += 1
                    stats[author]["project_names"].add(project_name)
                
                updated_at = mr.get("updated_at")
                if updated_at:
                    try:
                        dt = parse_datetime(updated_at)
                        if not stats[author]["last_activity"] or dt > stats[author]["last_activity"]:
                            stats[author]["last_activity"] = dt
                    except Exception:
                        pass
        
        # Check if we've reached the last page
            if len(mrs) < 100:  # Less than per_page means last page
                break
            page += 1

    except Exception as e:
        if debug_mode:
            st.write(f"Error processing commits for project {project_name}: {e}")
    
    # Get issues - MOVED OUTSIDE commits try block
    try:
        issues_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/issues"
        issues_params = {"created_after": since_date.isoformat(), "per_page": 100, "state": "all"}
        issues_result = safe_api_request(issues_url, headers, issues_params)
        
        if issues_result["success"]:
            issues = issues_result["data"]
            for issue in issues or []:
                author_info = issue.get("author", {})
                author = author_info.get("name", "Unknown")
                if author in valid_names:
                    stats[author]["issues"] += 1
                    stats[author]["project_names"].add(project_name)
                    
                    created_at = issue.get("created_at")
                    if created_at:
                        try:
                            dt = parse_datetime(created_at)
                            if not stats[author]["last_activity"] or dt > stats[author]["last_activity"]:
                                stats[author]["last_activity"] = dt
                        except Exception:
                            pass
    
    except Exception as e:
        if debug_mode:
            st.write(f"Error processing issues for project {project_name}: {e}")
    
    except Exception as e:
        if debug_mode:
            st.write(f"Error processing project {project_name}: {e}")


       


        # 🔵 GET PUSH EVENTS
        # 🔵 GET PUSH EVENTS - using safe paginated format
    # 🔵 GET PUSH EVENTS - Fixed
    try:
        events_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/events"
        events_params = {
            "action": "pushed",
            "per_page": 100,
        }

        page = 1
        while True:
            events_params["page"] = page
            events_result = safe_api_request(events_url, headers, events_params)

            if not events_result["success"]:
                if debug_mode:
                    st.write(f"❌ Failed to fetch push events on page {page}")
                break

            events = events_result["data"]
            if not events:
                break

            for event in events:
                author = event.get("author", {}).get("name", "Unknown")
                commit_count = event.get("push_data", {}).get("commit_count", 0)

                if debug_mode:
                    st.write(f"Push event: author={author}, commits={commit_count}, in valid_names={author in valid_names}")


                if author in valid_names:
                    stats[author]["push_events"] += 1
                    stats[author]["project_names"].add(project_name)

                    created_at = event.get("created_at")
                    if created_at:
                        try:
                            dt = parse_datetime(created_at)
                            if not stats[author]["last_activity"] or dt > stats[author]["last_activity"]:
                                stats[author]["last_activity"] = dt
                        except Exception:
                            pass

            if len(events) < 100:
                break
            page += 1

    except Exception as e:
        if debug_mode:
            st.write(f"Error processing push events for project {project_name}: {e}")



    
    return stats
