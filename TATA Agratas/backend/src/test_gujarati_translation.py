"""
Test script to verify Gujarati translation with Sarvam AI API
"""

import sys
from sarvam_translate import translate_to_english, translate_from_english
from logger_config import setup_logger

logger = setup_logger(__name__)

def test_gujarati_translation():
    """Test Gujarati to English and English to Gujarati translation"""
    
    print("=" * 80)
    print("GUJARATI TRANSLATION TEST")
    print("=" * 80)
    
    # Test 1: Gujarati to English
    print("\n📝 Test 1: Gujarati to English Translation")
    print("-" * 80)
    gujarati_text = "બેટરી કેવી રીતે બનાવવી?"
    print(f"Input (Gujarati): {gujarati_text}")
    
    result1 = translate_to_english(gujarati_text, 'gu-IN')
    print(f"Success: {result1.get('success', False)}")
    print(f"Output (English): {result1.get('translated_text', 'N/A')}")
    if not result1.get('success'):
        print(f"❌ Error: {result1.get('error', 'Unknown error')}")
    else:
        print("✅ Translation successful!")
    
    # Test 2: English to Gujarati
    print("\n📝 Test 2: English to Gujarati Translation")
    print("-" * 80)
    english_text = "Battery manufacturing involves several key steps including electrode preparation, cell assembly, and quality testing."
    print(f"Input (English): {english_text}")
    
    result2 = translate_from_english(english_text, 'gu-IN')
    print(f"Success: {result2.get('success', False)}")
    print(f"Output (Gujarati): {result2.get('translated_text', 'N/A')}")
    if not result2.get('success'):
        print(f"❌ Error: {result2.get('error', 'Unknown error')}")
    else:
        print("✅ Translation successful!")
    
    # Test 3: Check if translation actually changed the text
    print("\n📝 Test 3: Verify Translation Changed Text")
    print("-" * 80)
    if result2.get('success'):
        if result2['translated_text'] == english_text:
            print("⚠️  WARNING: Translated text is identical to English text!")
            print("This suggests translation may not be working properly.")
        else:
            print("✅ Translation produced different text (expected behavior)")
    
    # Test 4: Try with just 'gu' instead of 'gu-IN'
    print("\n📝 Test 4: Test with 'gu' instead of 'gu-IN'")
    print("-" * 80)
    print(f"Input (English): {english_text}")
    
    # Temporarily modify the language code
    result3 = translate_from_english(english_text, 'gu')
    print(f"Success: {result3.get('success', False)}")
    print(f"Output (Gujarati): {result3.get('translated_text', 'N/A')}")
    if not result3.get('success'):
        print(f"❌ Error: {result3.get('error', 'Unknown error')}")
    else:
        print("✅ Translation successful!")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Test 1 (gu-IN → en-IN): {'✅ PASS' if result1.get('success') else '❌ FAIL'}")
    print(f"Test 2 (en-IN → gu-IN): {'✅ PASS' if result2.get('success') else '❌ FAIL'}")
    print(f"Test 3 (Text Changed): {'✅ PASS' if (result2.get('success') and result2['translated_text'] != english_text) else '❌ FAIL'}")
    print(f"Test 4 (en-IN → gu): {'✅ PASS' if result3.get('success') else '❌ FAIL'}")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if not result2.get('success'):
        print("❌ Gujarati translation is NOT working with Sarvam API")
        print("\nPossible causes:")
        print("1. Sarvam API may not support Gujarati (gu-IN)")
        print("2. API key may be invalid or expired")
        print("3. Network connectivity issues")
        print("4. API rate limits exceeded")
        print("\nNext steps:")
        print("- Check Sarvam AI documentation for supported languages")
        print("- Verify API key is valid")
        print("- Contact Sarvam AI support")
    elif result2['translated_text'] == english_text:
        print("⚠️  Translation API responds but returns English text")
        print("\nPossible causes:")
        print("1. Language code 'gu-IN' may not be recognized")
        print("2. API may be falling back to English")
        print("\nNext steps:")
        print("- Try using 'gu' instead of 'gu-IN'")
        print("- Check Sarvam API documentation for correct language codes")
    else:
        print("✅ Gujarati translation is working correctly!")
        print("\nThe issue may be in the application flow, not the API.")
        print("Check the backend logs when making a voice query.")

if __name__ == "__main__":
    test_gujarati_translation()

# Made with Bob
