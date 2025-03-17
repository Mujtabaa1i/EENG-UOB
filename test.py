import os
import hashlib
import time
from datetime import datetime
import internetarchive
import sys
import re
from pathlib import Path
import subprocess  # Add this import at the top with others

# Add to configuration section
PUSH_STATE_FILE = ".push_state"  # Hidden state file

# Configuration
DEFAULT_UPLOAD_SPEED = 5  # MB/s
MAX_FILE_SIZE_MB = 500       # Archive.org file size limit
UPLOAD_RETRIES = 2

# Add these new functions
def check_pending_push():
    """Check if previous push attempt failed"""
    return os.path.exists(PUSH_STATE_FILE)

def create_push_flag():
    """Create state file indicating push needed"""
    with open(PUSH_STATE_FILE, 'w') as f:
        f.write(datetime.now().isoformat())

def clear_push_flag():
    """Remove push state file"""
    if os.path.exists(PUSH_STATE_FILE):
        os.remove(PUSH_STATE_FILE)


def calculate_md5(file_path):
    """Calculate MD5 hash of a file"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_existing_hashes():
    """Read existing hashes from uploaded.log"""
    hashes = set()
    if os.path.exists('uploaded.log'):
        with open('uploaded.log', 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 5:
                    hashes.add(parts[3])
    return hashes

def estimate_upload_time(total_size_mb):
    """Estimate upload time with speed test or default"""
    try:
        import speedtest
        st = speedtest.Speedtest()
        st.get_best_server()
        upload_speed = st.upload() / 8 / 1024 / 1024  # Convert to MB/s
        return total_size_mb / upload_speed
    except:
        return total_size_mb / DEFAULT_UPLOAD_SPEED

def generate_html():
    """Generate GitHub Pages HTML with file structure"""
    if not os.path.exists('uploaded.log'):
        print("ℹ️ No uploaded files - skipping HTML generation")
        return False

    structure = {}
    with open('uploaded.log', 'r') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) != 5:
                continue
            item_id, uploader, path, md5, ts = parts
            parts = path.split('/')
            current = structure.setdefault(uploader, {})
            for p in parts[:-1]:
                current = current.setdefault(p, {})
            current[parts[-1]] = f"https://archive.org/download/{item_id}/{path}"

    html = """<!DOCTYPE html>
<html>
<head>
    <title>🌐 Archive Uploads</title>
    <style>
        body { font-family: sans-serif; line-height: 1.6; }
        .folder { color: #2c3e50; }
        .file { color: #34495e; }
        ul { list-style: none; padding-left: 20px; }
        li { margin: 5px 0; }
        a { color: #2980b9; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>📁 Archived Files</h1>"""

    def build_tree(items, level=0):
        tree = ""
        for name, value in items.items():
            if isinstance(value, dict):
                tree += f"<li>📁 {name}\n<ul>{build_tree(value, level+1)}</ul></li>"
            else:
                tree += f'<li>📄 <a href="{value}">{name}</a></li>'
        return tree

    for uploader, data in structure.items():
        html += f"\n<h2>👤 Uploader: {uploader}</h2>\n<ul>{build_tree(data)}</ul>"

    html += "\n</body>\n</html>"
    
    with open('index.html', 'w') as f:
        f.write(html)
    
    create_push_flag()  # Mark that we have new content
    return True

# Add this new function
def push_to_github():
    """Push index.html to GitHub Pages repository"""
    print("\n" + "="*40)
    print("🚀 GitHub Pages Deployment")
    print("="*40)
    
    try:
        # Get repository URL
        try:
            result = subprocess.run(['git', 'remote', 'get-url', 'origin'], 
                                   capture_output=True, text=True, check=True)
            repo_url = result.stdout.strip()
        except subprocess.CalledProcessError:
            print("❌ No Git remote named 'origin' found")
            print("First run these commands in your project directory:")
            print("1. git init")
            print(f"2. git remote add origin https://github.com/Mujtabaa1i/EENG-UOB.git")
            return

        # Improved regex pattern for SSH/HTTPS URLs
        match = re.search(
            r"(?:https://github\.com/|git@github\.com:)([^/]+)/([^/.]+)(?:\.git)?",
            repo_url
        )
        
        if not match:
            print(f"❌ Could not parse GitHub URL: {repo_url}")
            print("Valid URL formats should look like:")
            print("HTTPS: https://github.com/username/repo-name")
            print("SSH: git@github.com:username/repo-name.git")
            return
            
        username, repo_name = match.groups()
        pages_url = f"https://{username}.github.io/{repo_name}/"
        
        # Check GitHub Pages branch
        print(f"\n🔗 Your GitHub Pages URL should be:")
        print(f"   {pages_url}")
        print("   (Note: Make sure GitHub Pages is enabled in repo settings)")
        
        # Get current branch
        branch_result = subprocess.run(['git', 'branch', '--show-current'],
                                      capture_output=True, text=True, check=True)
        current_branch = branch_result.stdout.strip()
        
        # Determine publish branch
        publish_branch = 'gh-pages' if 'gh-pages' in subprocess.getoutput('git branch') else 'main'
        if current_branch != publish_branch:
            print(f"\n⚠️  You're on '{current_branch}' branch but GitHub Pages might need '{publish_branch}'")
            if input(f"Switch to '{publish_branch}' branch? (Y/N): ").upper() == 'Y':
                subprocess.run(['git', 'checkout', publish_branch], check=True)

        # Git operations
        print("\n⏳ Committing index.html...")
        subprocess.run(['git', 'add', 'index.html'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Update GitHub Pages'], check=True)
        
        print(f"⏳ Pushing to {publish_branch} branch...")
        subprocess.run(['git', 'push', 'origin', publish_branch], check=True)
        
        print("\n✅ Successfully pushed to GitHub Pages!")
        print(f"🌍 Your files should be available at:")
        print(f"   {pages_url}")
        print("   (Might take 1-2 minutes to update)")

        clear_push_flag()
    except Exception as e:
        create_push_flag()
        raise

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error: {e.stderr}")
        print("Troubleshooting tips:")
        print("1. Ensure GitHub Pages is enabled in repo settings")
        print("2. Verify you have push permissions")
        print("3. Check your Git remote: git remote -v")

def main():
    print("\n" + "="*40)
    print("🚀 Archive.org Upload Script")
    print("="*40 + "\n")

    # Get user input
    path = input("📁 Enter path to upload: ").strip()
    if not os.path.isdir(path):
        print("❌ Invalid path!")
        return

    # Check existing hashes
    existing_hashes = get_existing_hashes()
    total_size = 0
    files_to_upload = []

    # Scan directory
    print("\n🔍 Scanning files...")
    for root, _, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, path)
            
            # Check file size
            file_size = os.path.getsize(file_path) / (1024**2)
            if file_size > MAX_FILE_SIZE_MB:
                print(f"❌ File too big: {rel_path} ({file_size:.2f}MB)")
                continue
                
            # Check MD5
            file_md5 = calculate_md5(file_path)
            if file_md5 in existing_hashes:
                print(f"⏩ Skipping {rel_path} (already uploaded)")
                continue
                
            files_to_upload.append((file_path, rel_path, file_md5))
            total_size += os.path.getsize(file_path)

    # Calculate stats
    total_size_mb = total_size / (1024**2)
    if total_size_mb == 0:
        print("\n✅ All files already uploaded!")
        return

    # Estimate time
    time_sec = estimate_upload_time(total_size_mb)
    print(f"\n📊 Found {len(files_to_upload)} files ({total_size_mb:.2f}MB)")
    print(f"⏳ Estimated upload time: {time_sec/60:.1f} minutes")

    # Confirmation
    if input("\n🚀 Start upload? (Y/N): ").strip().upper() != 'Y':
        print("❌ Upload cancelled")
        return

    # Get uploader info
    uploader = input("\n👤 Enter uploader name: ").strip()
    if not uploader:
        print("❌ Uploader name required!")
        return

    # Create item ID
    base_name = re.sub(r'[^a-zA-Z0-9-]', '_', os.path.basename(path))
    item_id = f"{uploader}_{base_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Upload files
    print("\n" + "="*40)
    print("⬆️ Starting upload process...")
    print("="*40 + "\n")

    session = internetarchive.get_session()
    success_count = 0

    for idx, (file_path, rel_path, md5) in enumerate(files_to_upload, 1):
        remote_name = rel_path.replace(os.path.sep, '/')
        print(f"📤 Uploading ({idx}/{len(files_to_upload)}): {rel_path}")

        for attempt in range(UPLOAD_RETRIES + 1):
            try:
                item = session.get_item(item_id)
                # Create proper IA file path format
                ia_path = remote_name.replace('\\', '/')  # Force Unix-style paths
                
                # Validate file exists
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Local file missing: {file_path}")

                # Add rate limiting
                time.sleep(10)

                item.upload(
                    {ia_path: file_path},  # Key=remote, Value=local
                    metadata={
                        'title': f"{uploader}'s Upload: {os.path.basename(path)}",
                        'mediatype': 'data',
                        'collection': 'opensource',
                        'description': f"Uploaded via Python script by {uploader}",
                        'creator': uploader,
                        'subject': 'user-upload',
                        'licenseurl': 'http://creativecommons.org/publicdomain/zero/1.0/'
                    },
                    verbose=True
                )
                with open('uploaded.log', 'a') as f:
                    f.write(f"{item_id}|{uploader}|{remote_name}|{md5}|{datetime.now().isoformat()}\n")
                success_count += 1
                print("✅ Upload succeeded")
                break
            except Exception as e:
                if attempt == UPLOAD_RETRIES:
                    print(f"❌ Final upload failure: {str(e)}")
                    with open('Failed.log', 'a') as f:
                        f.write(f"{datetime.now()}|{item_id}|{remote_name}|{md5}|{str(e)}\n")
                else:
                    print(f"⚠️  Attempt {attempt+1} failed: {str(e)}")
                    time.sleep(5)

    # Generate report
    print("\n" + "="*40)
    print(f"📊 Upload complete! Success: {success_count}/{len(files_to_upload)}")
    
    # After upload completion
    html_generated = generate_html()
    print("🌐 Generated index.html for GitHub Pages")

    # Check if we should prompt for push
    push_needed = False
    if html_generated:
        push_needed = True
    elif check_pending_push() and os.path.exists('index.html'):
        print("\n💡 Previous HTML update wasn't pushed to GitHub Pages")
        push_needed = True

    if push_needed:
        if input("\n🚀 Push to GitHub Pages? (Y/N): ").strip().upper() == 'Y':
            try:
                push_to_github()
                clear_push_flag()
            except:
                create_push_flag()
                raise

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")