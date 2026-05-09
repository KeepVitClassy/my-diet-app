import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime
import random
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

# ==========================================
# 0. 기본 설정 및 데이터베이스 로드
# ==========================================
api_key = st.secrets["GEMINI_API_KEY"]

# 회원 정보 파일(users.csv)이 없으면 빈 파일 만들기
if not os.path.exists('users.csv'):
    df = pd.DataFrame(columns=['user_id', 'password', 'diet_goal', 'allergies'])
    df.to_csv('users.csv', index=False)

# ✨ 수정된 부분: 앱 코드를 가볍게 유지하기 위해 외부 JSON 파일에서 레시피 DB 불러오기!
with open('recipes.json', 'r', encoding='utf-8') as f:
    recipes_db = json.load(f)

# 기억 상자에 '로그인 상태' 기록 만들기
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

st.title("🍽️ Myte")

# ==========================================
# 1. 로그인 전 화면 (회원가입 / 로그인)
# ==========================================
if not st.session_state['logged_in']:
    # 화면을 두 개의 탭으로 나누기
    tab1, tab2 = st.tabs(["🔑 로그인", "📝 회원가입"])
    
    with tab1:
        st.subheader("로그인")

        # ✨ [여기서부터 수정!] 원래 있던 위아래 입력창을 지우고 컬럼으로 바꿈
        col1, col2 = st.columns(2)
        with col1:
            login_id = st.text_input("아이디", key="login_id")
        with col2:
            login_pw = st.text_input("비밀번호", type="password", key="login_pw")
            
        st.write("") # 버튼 위에 공간 살짝 띄워주기
        
        # 버튼도 화면 꽉 차게 예쁘게 늘림 (use_container_width=True)
        if st.button("로그인하기", use_container_width=True):
            users_df = pd.read_csv('users.csv')
            # 아이디와 비밀번호가 일치하는 회원이 있는지 확인
            user_match = users_df[(users_df['user_id'] == login_id) & (users_df['password'] == login_pw)]
            
            if not user_match.empty:
                # 로그인 성공! 회원 정보를 기억 상자에 저장하고 화면 새로고침
                st.session_state['logged_in'] = True
                st.session_state['current_user'] = login_id
                st.session_state['user_goal'] = user_match.iloc[0]['diet_goal']
                
                # 알레르기 정보가 비어있을(NaN) 경우를 대비한 안전 처리
                saved_allergies = user_match.iloc[0]['allergies']
                st.session_state['user_allergies'] = saved_allergies if pd.notna(saved_allergies) else ""
                
                st.rerun() # 화면을 즉시 새로고침해서 메인 화면으로 넘김!
            else:
                st.error("아이디 또는 비밀번호가 틀렸습니다.")
                
    with tab2:
        st.subheader("새로 오셨군요! 프로필을 설정해 주세요.")
        new_id = st.text_input("새 아이디")
        new_pw = st.text_input("새 비밀번호", type="password")
        new_goal = st.selectbox("어떤 목표의 식단을 원하시나요?", ["저속노화", "다이어트", "고혈압 관리", "임산부 건강"])
        new_allergies = st.text_input("못 먹는 재료나 알러지가 있나요? (쉼표로 구분, 없으면 빈칸)")
        
        if st.button("회원가입 완료"):
            users_df = pd.read_csv('users.csv')
            if new_id in users_df['user_id'].values:
                st.error("이미 존재하는 아이디입니다. 다른 아이디를 입력해 주세요.")
            elif new_id and new_pw:
                # 새 회원 정보 저장
                new_user = pd.DataFrame([{
                    'user_id': new_id, 'password': new_pw, 
                    'diet_goal': new_goal, 'allergies': new_allergies
                }])
                users_df = pd.concat([users_df, new_user], ignore_index=True)
                users_df.to_csv('users.csv', index=False)
                st.success("회원가입이 완료되었습니다! 위 탭에서 로그인해 주세요. 🎉")
            else:
                st.warning("아이디와 비밀번호를 모두 입력해 주세요.")

# ==========================================
# 2. 로그인 후 화면 (메인 서비스)
# ==========================================
else:
    # 사이드바에 내 프로필과 메뉴, 로그아웃 버튼 표시
    with st.sidebar:
        st.header(f"👤 {st.session_state['current_user']}님 환영합니다!")
        st.write(f"🎯 **나의 목표:** {st.session_state['user_goal']}")
        if st.session_state['user_allergies']:
            st.write(f"🚫 **알러지:** {st.session_state['user_allergies']}")
        
        st.divider()
        # ✨ 여기에 메뉴 선택 라디오 버튼이 추가되었어!
        app_mode = st.radio("메뉴 선택", ["레시피 추천받기", "나의 식단 기록"])

        st.divider()
        if st.button("로그아웃"):
            # 기억 상자 비우고 화면 새로고침하여 로그인 화면으로 돌아감
            st.session_state.clear()
            st.rerun()

    # ==========================================
    # ✨ 화면 분기점: '나의 식단 기록'을 눌렀을 때
    # ==========================================
    if app_mode == "나의 식단 기록":
        st.header(f"📖 {st.session_state['current_user']}님의 건강 장부")
        file_path = f"{st.session_state['current_user']}.csv"
        
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values(by='date', ascending=False)
                
                # ✨ 1. None(결측치)을 '기록 없음'으로 깔끔하게 채워주기!
                df = df.fillna("기록 없음")
                
                # ✨ 2. 사용자가 보기 편하게 영어 열 이름을 한글로 바꾸기!
                df = df.rename(columns={
                    'date': '날짜',
                    'goal': '식단 목표',
                    'recipe_name': '요리 이름',
                    'used_ingredients': '사용된 재료',
                    'recipe_instructions': 'AI 조리법'
                })
                
                st.write("그동안 기록하신 식단 목록입니다. 어떤 멋진 요리들을 해드셨는지 확인해 보세요! 💪")
                st.dataframe(df, use_container_width=True) 
                
                total_count = len(df)
                st.info(f"현재까지 총 **{total_count}개**의 식단이 기록되었습니다. 대단해요! 🎉")
            else:
                st.warning("아직 기록된 식단이 없습니다. 레시피를 추천받고 첫 기록을 남겨보세요!")
        else:
            st.info("기록된 장부 파일이 없습니다. 레시피 추천 후 '기록하기' 버튼을 눌러주세요.")

    # ==========================================
    # ✨ 화면 분기점: '레시피 추천받기'를 눌렀을 때 (기존 로직 전체)
    # ==========================================
    else:
        st.header("🍳 AI 식단 비서 Myte")
        st.info("프로필에 설정된 목표와 알러지 정보를 바탕으로 AI가 알아서 추천해 줍니다.")
        ingredients = st.text_input("현재 냉장고에 있는 재료를 쉼표(,)로 구분해서 적어주세요.")
        
        if st.button("레시피 추천받기"):
            if ingredients:
                # 0. 알레르기 재료 즉시 제거 (파이썬 철통 보안)
                my_allergies = st.session_state['user_allergies']
                if my_allergies:
                    allergy_list = [a.strip() for a in my_allergies.split(",")]
                    original_ing_list = [i.strip() for i in ingredients.split(",")]
                    safe_user_ing_list = [
                        ing for ing in original_ing_list 
                        if not any(allergy in ing for allergy in allergy_list)
                    ]
                    
                    if len(original_ing_list) != len(safe_user_ing_list):
                        removed_items = set(original_ing_list) - set(safe_user_ing_list)
                        st.warning(f"🚫 알레르기 유발 재료({', '.join(removed_items)})는 안전을 위해 추천 재료에서 제외되었습니다.")
                        ingredients = ", ".join(safe_user_ing_list) # 깨끗해진 재료로 업데이트!

                # ==========================================
                # ✨ [부활한 안전 금고!] 알레르기가 싹 걸러진 '진짜 안전한 재료'를 영구 보관!
                st.session_state['safe_ingredients'] = ingredients
                # ==========================================

                # 🚨 1. 불량식품 판독기 (입구컷)
                junk_food_list = ["불닭", "라면", "피자", "치킨", "콜라", "과자", "초콜릿", "아이스크림", "햄버거", "마라탕", "탕후루", "젤리", "족발"]
                # ... (이하 기존 코드) ...
                
                # 🚨 1. 불량식품 판독기 (입구컷)
                junk_food_list = ["불닭", "라면", "피자", "치킨", "콜라", "과자", "초콜릿", "아이스크림", "햄버거", "마라탕", "탕후루", "젤리", "족발"]
                # ... (이하 기존 코드 그대로) ...
                clean_input = ingredients.replace(" ", "")
                is_junk_included = any(junk in clean_input for junk in junk_food_list)
                
                if is_junk_included:
                    st.error("🚨 삐빅! 건강을 위한 앱입니다. 인스턴트나 정크푸드는 냉장고에서 살포시 빼주세요! 🙅‍♀️")
                    st.stop() # ✨ 여기서 프로그램 실행을 딱 멈춤! (아래 코드는 쳐다보지도 않음)
                
                # ==========================================
                # 🟢 불량식품이 없을 때만 아래 코드가 자연스럽게 실행됨!
                # ==========================================
                my_goal = st.session_state['user_goal']
                my_allergies = st.session_state['user_allergies']
                
                # 1. 목표 및 알레르기 필터링
                target_recipes = [r for r in recipes_db if my_goal in r.get("targets", [])]
                    
                safe_recipes = [] 
                if my_allergies: 
                    allergy_list = [a.strip() for a in my_allergies.split(",")] 
                    for recipe in target_recipes: 
                        is_safe = True
                        for ingredient in recipe["ingredients"]:
                            for allergy in allergy_list:
                                if allergy in ingredient:
                                    is_safe = False
                        if is_safe:
                            safe_recipes.append(recipe)
                else:
                    safe_recipes = target_recipes 

                # 2. 양념 제외 핵심 재료 매칭
                user_ing_list = [i.strip() for i in ingredients.split(",")]
                base_seasonings = ["소금", "후추", "올리브유", "설탕", "간장", "참기름", "다진마늘", "들기름"]
                
                scored_recipes = []
                for recipe in safe_recipes:
                    main_match_count = 0
                    for r_ing in recipe["ingredients"]:
                        if r_ing in base_seasonings:
                            continue 
                            
                        for u_ing in user_ing_list:
                            if r_ing in u_ing or u_ing in r_ing:
                                main_match_count += 1
                                break 
                    
                    if main_match_count > 0:
                        scored_recipes.append({"recipe": recipe, "score": main_match_count})
                
                scored_recipes.sort(key=lambda x: x["score"], reverse=True)
                valid_recipes = [item["recipe"] for item in scored_recipes]

                # 3. 최대 3개 추출 및 🌟플랜 A / 플랜 B 하이브리드 로직🌟
                if not valid_recipes:
                    # [🚨 플랜 B: DB에 일치하는 재료가 없을 때 (비상 AI 창작 가동!)]
                    st.info("💡 DB에 딱 맞는 레시피가 없네요. 대신 입력하신 재료만으로 특별한 맞춤형 요리를 창작해 드릴게요!")
                    
                    with st.spinner("AI가 새로운 요리를 발명 중입니다... 뚝딱뚝딱 🍳"):
                        llm = ChatGoogleGenerativeAI(
                            model="gemini-2.5-flash",
                            google_api_key=api_key,
                            temperature=0,        # 👈 [추가 1] 고민하지 마! 가장 뻔하고 정확한 대답만 0.1초 만에 뱉어! (0~1 사이, 0일수록 빠르고 기계적임)
                            max_tokens=60
                            )
                        
                        fallback_prompt = PromptTemplate(
                            # ✨ 1. 변수에 allergies 추가
                            input_variables=["ingredients", "diet_goal", "allergies"],
                            template="""
                            당신은 {diet_goal} 식단을 연구하는 전문 AI 요리사입니다.
                            사용자의 냉장고 재료: {ingredients}
                            사용자의 알러지 정보: {allergies}
                            
                            [🚨가장 중요한 1순위: 식용 판별 및 알러지 규칙🚨]
                            1. 먼저 사용자가 입력한 재료가 실제로 먹을 수 있는 '식재료'인지 판단하세요. 비식품이 있다면 "NON_FOOD"라고만 출력하세요! 
                            2. 🚨사용자의 알러지 정보({allergies})에 해당하는 단어는 요리 이름에 절대, 단 한 글자도 쓰지 마세요!🚨

                            [일반 창작 규칙]
                            만약 정상적인 식재료가 맞다면, 사용자가 가진 재료만 활용해서 {diet_goal}에 맞는 건강하고 기발한 요리 이름 3개를 창작해주세요.
                            - 반드시 요리이름 / 요리이름 / 요리이름 형식으로 슬래시(/)를 넣어서 한 줄로만 대답하세요.
                            - 부연 설명, 숫자('1.'), '1번새이름:' 같은 기호는 절대 쓰지 마세요.
                            """
                        )
                        fallback_chain = fallback_prompt | llm
                        res = fallback_chain.invoke({
                            "ingredients": ingredients,
                            "diet_goal": my_goal,
                            "allergies": my_allergies # ✨ 2. 파이썬 변수 전달!
                        })
                        
                        # ✨ 파이썬이 AI의 대답을 듣고 문지기 역할을 함!
                        if "NON_FOOD" in res.content:
                            st.error("🚨 삐빅! 요리할 수 없는 물건(비식재료)이 감지되었습니다. 진짜 냉장고에 있는 식재료만 입력해 주세요! 🤖")
                            st.stop() # 여기서 멈춰서 엉뚱한 요리가 생성되는 걸 완벽 차단!
                            
                        # 정상적인 재료라면 기존처럼 슬래시 쪼개기 진행
                        raw_names = res.content.replace('"', '').replace('*', '').strip()
                        new_names = [name.strip() for name in raw_names.split('/') if name.strip()]
                        
                        # 파이썬 지우개 (깔끔한 이름 만들기)
                        clean_names = []
                        for name in new_names:
                            if ":" in name:
                                name = name.split(":")[-1].strip()
                            clean_names.append(name)
                            
                        if len(clean_names) != 3:
                            clean_names = ["건강 맞춤 볶음", "영양 가득 샐러드", "가벼운 다이어트 구이"] 
                            
                        adapted_candidates = []
                        for name in clean_names:
                            mock_recipe = {
                                "name": "AI 창작 맞춤 요리",
                                "ingredients": [i.strip() for i in ingredients.split(",")],
                                "instructions": ["AI가 사용자의 냉장고 재료만으로 실시간 창작한 레시피입니다."]
                            }
                            adapted_candidates.append({
                                "original_recipe": mock_recipe,
                                "display_name": name
                            })
                            
                    st.session_state['candidates'] = adapted_candidates
                    if 'ai_result' in st.session_state:
                        del st.session_state['ai_result']
                        
                else:
                    # [🟢 플랜 A: 기존처럼 DB에서 찾았을 때 (택배 합배송 방식)]
                    recommend_count = min(3, len(valid_recipes))
                    picked_recipes = valid_recipes[:recommend_count]
                    
                    with st.spinner("AI가 냉장고 재료에 맞춰 메뉴를 고민 중입니다... 뚝딱뚝딱 🍳"):
                        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
                        
                        recipes_info = ""
                        for i, recipe in enumerate(picked_recipes):
                            ing_str = ", ".join(recipe["ingredients"])
                            recipes_info += f"[{i+1}번] {recipe['name']} (원래 재료: {ing_str})\n"

                        rename_prompt = PromptTemplate(
                            # ✨ 1. 변수에 allergies 추가
                            input_variables=["ingredients", "recipes_info", "count", "allergies"],
                            template="""
                            사용자의 냉장고 재료: {ingredients}
                            사용자의 알러지 정보: {allergies}
                            
                            아래 {count}개의 원본 레시피를 보고, 사용자의 재료를 바탕으로 
                            '새로운 요리의 이름'을 각각 지어주세요.
                            
                            [🚨이름 작명 엄격 규칙🚨]
                            1. 🚨[매우 중요] 사용자의 알러지 정보({allergies})에 해당하는 단어는 새 이름에 절대, 단 한 글자도 들어가면 안 됩니다! 원본 레시피 이름에 있더라도 무조건 빼세요.🚨
                            1. 새 요리 이름은 반드시 사용자가 입력한 재료({ingredients})의 단어를 직접 조합해서 직관적으로 지으세요. (예: 가지 닭가슴살 볶음, 양배추 토마토 스튜 등)
                            2. 원본 레시피 이름에 있더라도, 사용자가 입력하지 않은 식재료(예: 두부면, 파스타 면, 참치, 치즈 등) 단어는 새 이름에 **절대 한 글자도** 들어가면 안 됩니다! 무조건 빼세요.
                            3. 기본 양념(소금, 간장, 식초, 설탕, 후추, 기름)은 이름에 포함해도 됩니다.
                            4. 🚨 '1번새이름:', '1.', '-' 같은 숫자나 기호, 부연 설명은 절대 쓰지 마세요. 오직 순수한 요리 이름만 슬래시(/)로 연결해 딱 한 줄로 출력하세요.
                            """
                        )

                        rename_chain = rename_prompt | llm
                        res = rename_chain.invoke({
                            "ingredients": ingredients,
                            "recipes_info": recipes_info,
                            "count": len(picked_recipes),
                            "allergies": my_allergies # ✨ 2. 파이썬 변수 전달!
                        })
                        
                        raw_names = res.content.replace('"', '').replace('*', '').strip()
                        new_names = [name.strip() for name in raw_names.split('/') if name.strip()]
                        
                        if len(new_names) != len(picked_recipes):
                            new_names = [r["name"] for r in picked_recipes]
                            
                        adapted_candidates = []
                        for i in range(len(picked_recipes)):
                            adapted_candidates.append({
                                "original_recipe": picked_recipes[i],
                                "display_name": new_names[i]
                            })
                    
                    st.session_state['candidates'] = adapted_candidates
                    if 'ai_result' in st.session_state:
                        del st.session_state['ai_result']
            else:
                st.warning("재료를 먼저 입력해 주세요!")

        # ---------------------------------------------------------
        # 후보 보여주기 및 선택
        if 'candidates' in st.session_state:
            st.divider()
            st.write("### 🧑‍🍳 AI가 내 냉장고에 맞춘 추천 메뉴!")
            
            # 라디오 버튼에 AI가 지어준 새 이름만 깔끔하게 노출
            candidate_names = [c["display_name"] for c in st.session_state['candidates']]
            selected_name = st.radio("마음에 드는 레시피를 하나 선택해주세요:", candidate_names)
            
            if st.button("✨ 이 레시피로 자세히 보기"):
                # 선택한 새 이름과 매칭되는 원본 레시피 데이터를 꺼내옴
                selected_candidate = next(c for c in st.session_state['candidates'] if c["display_name"] == selected_name)
                base_recipe = selected_candidate["original_recipe"]
                
                with st.spinner(f"'{selected_name}' 요리법을 작성 중입니다..."):
                    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
                    
                    prompt_template = """
                    당신은 {diet_goal} 식단을 연구하는 전문 AI 요리사입니다.
                    사용자의 냉장고 재료: {ingredients}

                    [🚨기본 상비약 규칙🚨]
                    - 소금, 설탕, 간장, 식초, 후추, 식용유, 참기름, 쌀(밥), 물은 모든 집에 항상 구비되어 있다고 가정하고 레시피를 만드세요.
                    - 이 재료들은 사용자가 입력하지 않았더라도 조리에 필요하다면 자유롭게 사용하세요. 
                    - 절대 "기름이 없어서~" 같은 사과나 양해 멘트를 하지 마세요.

                    [재료 사용 엄격 규칙]
                    - 위 상비약을 제외한 메인 식재료(카레가루, 육류, 특정 채소 등)는 반드시 {ingredients}에 있는 것만 사용하세요.

                    요리 이름 [{selected_name}]에 맞춰 {diet_goal}에 좋은 건강한 조리법을 작성해주세요.
                    """

                    prompt = PromptTemplate(input_variables=["diet_goal", "ingredients", "selected_name", "recipe"], template=prompt_template)
                    chain = prompt | llm

                    safe_ing = st.session_state.get('safe_ingredients', ingredients)

                    # 안정망(try-except) 설치
                    try:
                        # 1. 일단 AI에게 요리법을 써달라고 시도해 봅니다.
                        result = chain.invoke({
                            "diet_goal": st.session_state['user_goal'],
                            "ingredients": ingredients, 
                            "selected_name": selected_name, 
                            "recipe": json.dumps(base_recipe, ensure_ascii=False)
                        })
                    
                        # 2. 에러 없이 성공했다면 결과를 저장합니다.
                        st.session_state['ai_result'] = result.content
                        st.session_state['final_recipe_name'] = selected_name
                        st.session_state['final_ingredients'] = safe_ing 

                    except Exception as e:
                        # 🚨 3. 만약 429 사용량 초과 에러가 발생했다면? 이쪽으로 도망옵니다!
                        st.error("🚨 앗! 현재 AI 요리사가 주문이 밀려(사용량 초과) 잠시 휴식 중입니다. 1~2분 뒤에 다시 시도해 주세요! 🥲")
                        st.stop() # 에러가 났으니 여기서 실행을 멈추고 빈 화면을 보여줍니다.
        

        # ---------------------------------------------------------
        # 최종 결과 출력 및 기록 저장 파트
        if 'ai_result' in st.session_state:
            st.success(f"짠! 선택하신 '{st.session_state['final_recipe_name']}' 요리법입니다.")
            st.write(st.session_state['ai_result'])
            
            if st.button("📍 이 레시피를 내 장부에 기록하기"):
                # ✨ 혹시라도 데이터가 비어있으면 안전하게 '알 수 없음'으로 저장!
                new_record = {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "goal": st.session_state.get('user_goal', '기본 목표'),
                    "recipe_name": st.session_state.get('final_recipe_name', '알 수 없음'),
                    "used_ingredients": st.session_state.get('final_ingredients', '알 수 없음'),
                    "recipe_instructions": st.session_state.get('ai_result', '내용 없음') 
                }
                
                file_path = f"{st.session_state['current_user']}.csv"
                # ... (아래 CSV 저장 코드는 기존과 동일!) ...
                if os.path.exists(file_path):
                    df = pd.read_csv(file_path)
                    df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
                else:
                    df = pd.DataFrame([new_record])
                    
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                st.success(f"나의 장부({file_path})에 성공적으로 기록되었습니다! 사이드바 메뉴에서 확인해 보세요. 📖")
