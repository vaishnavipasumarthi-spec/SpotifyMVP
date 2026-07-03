import os
from dotenv import load_dotenv

# Try to import the libraries
try:
    load_dotenv()
    import google.generativeai as genai
    
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("FAIL: GEMINI_API_KEY is missing or empty in .env")
        exit(1)
        
    print(f"SUCCESS: Found API key starting with: {gemini_key[:4]}... (length: {len(gemini_key)})")
    
    # Configure and try a simple dummy request to test authentication
    print("Testing authentication with Google API...")
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Generate content
    response = model.generate_content("Reply with the exact word 'Authenticated'.")
    print(f"API Response: {response.text.strip()}")
    print("ALL CHECKS PASSED: Your Gemini API Key is valid and working!")
    
except ImportError as e:
    print(f"Waiting for packages to install... {e}")
except Exception as e:
    print(f"API ERROR: {e}")
