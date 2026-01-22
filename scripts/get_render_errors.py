#!/usr/bin/env python3
"""
Fetch and display error logs from Render deployment.

Usage:
    python scripts/get_render_errors.py                  # Default service
    python scripts/get_render_errors.py daiy-web-prod    # Specific service
    python scripts/get_render_errors.py - errors.json    # Save to file
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_render_errors(
    service_name: str = "daiy-web-prod",
    output_file: str | None = None,
    limit: str | None = None,
    render_cmd: str | None = None,
):
    """
    Fetch error logs from Render deployment.
    
    Args:
        service_name: Render service name (default: daiy-web-prod)
        output_file: Optional file to save errors to
        limit: Max errors to fetch
    
    Returns:
        bool: True if successful, False otherwise
    """
    
    render_cli = render_cmd or os.environ.get("RENDER_CLI", "render")

    # Resolve full path for better error messages
    cli_path = shutil.which(render_cli)
    if not cli_path:
        print(f"❌ Render CLI '{render_cli}' not found on PATH")
        print("")
        print("Install the official Render CLI or set RENDER_CLI to your binary (e.g., raster3d):")
        print("  brew install render          # macOS/Linux (Homebrew)")
        print("  npm install -g @render-oss/cli  # If available")
        print("  or set RENDER_CLI=/path/to/cli if you installed raster3d")
        print("")
        print("Then authenticate:")
        print(f"  {render_cli} login")
        return False

    try:
        subprocess.run(
            [cli_path, "--version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
    except Exception:
        print(f"❌ Failed to execute '{render_cli}' (path: {cli_path})")
        print("Ensure the binary is executable and on PATH.")
        return False
    
    print(f"🔍 Fetching error logs from Render service: {service_name}")
    print()
    
    # Build command to run on Render
    cmd = "cd /app && python web/view_errors.py"
    
    if limit:
        cmd += f" --limit {limit}"
    
    cmd += " --export json"
    
    try:
        # Execute on Render via render ssh (or exec for other CLIs)
        print("📡 Connecting to Render...")
        
        # Try ssh first (render CLI), fall back to exec (other CLIs)
        ssh_result = subprocess.run(
            [cli_path, "ssh", service_name, cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        # If ssh command failed, try exec (for other Render CLIs)
        if ssh_result.returncode != 0 and "unknown command" in ssh_result.stderr:
            result = subprocess.run(
                [cli_path, "exec", "--service", service_name, cmd],
                capture_output=True,
                text=True,
                timeout=30,
            )
        else:
            result = ssh_result
        
        if result.returncode != 0:
            print(f"❌ Error: {result.stderr}")
            if "Service not found" in result.stderr or "Not found" in result.stderr:
                print("")
                print("💡 Check your service name:")
                print("   render services")
            return False
        
        # Parse JSON output
        try:
            errors = json.loads(result.stdout)
        except json.JSONDecodeError:
            print("❌ Failed to parse response from Render")
            print("Response:", result.stdout[:200])
            return False
        
        if not errors:
            print("✅ No errors found - everything is working!")
            print()
            return True
        
        # Display summary
        print(f"✅ Found {len(errors)} errors")
        print()
        print("=" * 70)
        
        # Group by error type
        by_type = {}
        for error in errors:
            error_type = error.get("error_type", "unknown")
            by_type.setdefault(error_type, 0)
            by_type[error_type] += 1
        
        print("Error Summary:")
        for error_type, count in sorted(by_type.items()):
            print(f"  • {error_type}: {count}")
        
        print()
        print("Recent errors:")
        print("=" * 70)
        
        # Show first 10 errors (or fewer if less available)
        display_count = min(10, len(errors))
        for i, error in enumerate(errors[:display_count], 1):
            print(f"\n[{i}] {error.get('error_type', 'UNKNOWN').upper()}")
            print(f"    Time: {error.get('timestamp', 'N/A')}")
            print(f"    Message: {error.get('error_message', 'N/A')[:80]}")
            if error.get("operation"):
                print(f"    Operation: {error.get('operation')}")
            if error.get("recovery_suggestion"):
                print(f"    Fix: {error.get('recovery_suggestion')}")
        
        if len(errors) > display_count:
            print(f"\n... and {len(errors) - display_count} more errors")
        
        print()
        print("=" * 70)
        
        # Save to file if requested
        if output_file:
            output_path = Path(output_file)
            output_path.write_text(json.dumps(errors, indent=2))
            print(f"✅ Saved {len(errors)} errors to: {output_file}")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Connection timeout - Render service may be unreachable")
        print("   Check if your service is running on Render dashboard")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    service = sys.argv[1] if len(sys.argv) > 1 else "daiy-web-prod"
    output = sys.argv[2] if len(sys.argv) > 2 else None
    limit = sys.argv[3] if len(sys.argv) > 3 else None

    # Handle "-" as placeholder for default (for make targets)
    if service == "-":
        service = "daiy-web-prod"

    # Allow override via environment
    render_cli = os.environ.get("RENDER_CLI")

    success = get_render_errors(service, output, limit, render_cli)
    sys.exit(0 if success else 1)
