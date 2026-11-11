#!/usr/bin/env python3
"""
🤖 Seletor de Testes com IA (versão CI/CD)

Este script usa a API do Google Gemini (grátis) para analisar
quais testes rodar no GitHub Actions.

Por que API na nuvem em vez de Ollama no CI?
- Ollama precisaria baixar 2GB+ de modelo a cada run
- APIs na nuvem respondem em <1 segundo
- Gemini e Groq são grátis com rate limit generoso

Uso:
    export GEMINI_API_KEY="sua-chave-aqui"
    python select_tests_ci.py

Obter chave grátis:
    - Gemini: https://aistudio.google.com/apikey
    - Groq (alternativa): https://console.groq.com
"""
import subprocess
import requests
import os
import sys
import json
from pathlib import Path


# ============================================================
# CONFIGURAÇÃO: Escolha qual API usar
# ============================================================
# Opção 1: Google Gemini (padrão)
# Opção 2: Groq (alternativa - descomente se preferir)
# ============================================================

USE_GEMINI = True  # Mude para False para usar Groq


def get_changed_files() -> str:
    """
    Pega lista de arquivos modificados.
    
    No CI, compara com o commit anterior (HEAD~1).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            capture_output=True, 
            text=True,
            check=True
        )
        files = result.stdout.strip()
        if files:
            return files
    except subprocess.CalledProcessError:
        pass
    
    return "Nenhum arquivo modificado"


def ask_gemini(changed_files: str) -> str:
    """
    Consulta a API do Google Gemini para sugestão de testes.
    
    Gemini é a IA do Google, grátis com 60 req/min.
    
    Args:
        changed_files: Lista de arquivos modificados
        
    Returns:
        Sugestão de testes da IA
    """
    
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ Erro: GEMINI_API_KEY não está configurada!")
        print("")
        print("Para configurar:")
        print("  1. Acesse https://aistudio.google.com/apikey")
        print("  2. Clique em 'Create API Key'")
        print("  3. export GEMINI_API_KEY='sua-chave'")
        print("")
        sys.exit(1)
    
    prompt = f"""Você é um assistente de CI/CD.

Arquivos modificados:
{changed_files}

Quais testes pytest devo rodar?

Regras:
- src/calculadora.py → tests/test_calculadora.py
- src/usuario.py → tests/test_usuario.py
- tests/*.py → o próprio arquivo

Responda APENAS os caminhos dos arquivos de teste, um por linha, sem explicação."""

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 200
                }
            },
            timeout=30
        )
        
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ Erro na API Gemini: {e}")
        print(f"   Response: {response.text}")
        sys.exit(1)


# ============================================================
# ALTERNATIVA: Groq API (descomente para usar)
# ============================================================
# def ask_groq(changed_files: str) -> str:
#     """
#     Consulta a API do Groq para sugestão de testes.
#     Groq roda modelos LLaMA com inferência ultra-rápida.
#     """
#     
#     api_key = os.environ.get("GROQ_API_KEY")
#     
#     if not api_key:
#         print("❌ Erro: GROQ_API_KEY não está configurada!")
#         print("  1. Acesse https://console.groq.com")
#         print("  2. Crie uma API Key")
#         print("  3. export GROQ_API_KEY='sua-chave'")
#         sys.exit(1)
#     
#     try:
#         response = requests.post(
#             "https://api.groq.com/openai/v1/chat/completions",
#             headers={
#                 "Authorization": f"Bearer {api_key}",
#                 "Content-Type": "application/json"
#             },
#             json={
#                 "model": "llama-3.1-8b-instant",
#                 "messages": [{
#                     "role": "system",
#                     "content": "Você é um assistente de CI/CD. Responda apenas com caminhos de arquivos de teste, um por linha."
#                 }, {
#                     "role": "user",
#                     "content": f"""Arquivos modificados:
# {changed_files}
# 
# Quais testes pytest devo rodar?
# Regras:
# - src/calculadora.py → tests/test_calculadora.py
# - src/usuario.py → tests/test_usuario.py
# 
# Responda APENAS os caminhos, sem explicação."""
#                 }],
#                 "temperature": 0.1,
#                 "max_tokens": 200
#             },
#             timeout=30
#         )
#         
#         response.raise_for_status()
#         data = response.json()
#         return data["choices"][0]["message"]["content"].strip()
#         
#     except requests.exceptions.HTTPError as e:
#         print(f"❌ Erro na API Groq: {e}")
#         sys.exit(1)
# ============================================================


def filter_valid_tests(suggestion: str) -> list:
    """
    Filtra a sugestão da IA para manter apenas arquivos de teste válidos.
    """
    valid_tests = []
    
    for line in suggestion.split('\n'):
        line = line.strip()
        # Ignorar linhas vazias ou que não são arquivos de teste
        if not line:
            continue
        if not line.startswith('tests/'):
            continue
        if not line.endswith('.py'):
            continue
        if 'pytest' in line.lower():
            continue
        
        # Verificar se o arquivo existe
        if Path(line).exists():
            valid_tests.append(line)
    
    return list(set(valid_tests))


def main():
    """Função principal para CI."""
    api_name = "Gemini" if USE_GEMINI else "Groq"
    
    print("=" * 50)
    print(f"🤖 Seletor de Testes com IA ({api_name} API)")
    print("=" * 50)
    print("")
    
    # 1. Pegar arquivos modificados
    print("🔍 Analisando mudanças...")
    changed_files = get_changed_files()
    print(f"📝 Modificados: {changed_files}")
    
    # 2. Consultar IA
    print(f"\n🤖 Consultando {api_name} API...")
    
    if USE_GEMINI:
        suggestion = ask_gemini(changed_files)
    else:
        # Descomente a função ask_groq acima para usar
        # suggestion = ask_groq(changed_files)
        print("❌ Groq não está habilitado. Descomente a função ask_groq.")
        sys.exit(1)
    
    # 3. Filtrar apenas testes válidos
    valid_tests = filter_valid_tests(suggestion)
    
    if not valid_tests:
        print("\n⚠️  Nenhum teste válido sugerido.")
        valid_tests = []
    
    # 4. Mostrar resultado
    print(f"\n✅ Testes a executar:")
    for test in valid_tests:
        print(f"  {test}")
    
    # 5. Salvar para uso no workflow
    with open("suggested_tests.txt", "w") as f:
        f.write("\n".join(valid_tests))
    
    print("\n📄 Salvo em: suggested_tests.txt")


if __name__ == "__main__":
    main()
