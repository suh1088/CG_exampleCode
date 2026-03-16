# =============================================================================
# 3-hello-triangle.py
# 목적: PyOpenGL + GLFW를 사용하여 화면에 흰색 삼각형 하나를 렌더링하는
#       가장 기본적인 OpenGL 프로그램.
#
# 핵심 OpenGL 파이프라인 흐름:
#   [CPU 메모리] vertices(좌표 배열)
#       → VBO(GPU 버퍼에 데이터 업로드)
#       → VAO(버퍼 레이아웃 설명 저장)
#       → Vertex Shader(정점 위치 → 클립 공간)
#       → 래스터화(삼각형 내부를 픽셀로 분할)
#       → Fragment Shader(각 픽셀에 색상 지정)
#       → 프레임버퍼(화면 출력)
# =============================================================================

from OpenGL.GL import *   # PyOpenGL: GPU에 명령을 내리는 OpenGL 함수 전체 임포트
from glfw.GLFW import *   # GLFW: 창 생성 · OpenGL 컨텍스트 · 키보드/마우스 이벤트 처리
import glm                # GLM: 벡터·행렬 연산 및 GPU 호환 배열(glm.array) 생성

# =============================================================================
# [셰이더 소스 코드]
# 셰이더란? GPU에서 실행되는 작은 프로그램으로, GLSL(OpenGL Shading Language)로 작성됨.
# OpenGL 렌더링 파이프라인에서 프로그래머가 직접 제어할 수 있는 두 단계:
#   1) Vertex Shader  : 정점(꼭짓점)마다 한 번씩 실행 → 위치 변환 담당
#   2) Fragment Shader: 픽셀(프래그먼트)마다 한 번씩 실행 → 색상 결정 담당
# =============================================================================

# 버텍스 셰이더 소스 (GLSL): 각 정점(vertex)의 클립 공간 위치를 계산, 정점마다 GPU에서 실행
g_vertex_shader_src = '''
#version 330 core   // OpenGL 3.3 Core Profile 용 GLSL 버전 지정

// input vertex position. its attribute index is 0.
layout (location = 0) in vec3 vin_pos;
// layout(location=0): VAO에서 attribute index 0번 슬롯과 연결됨을 선언.
// in vec3 vin_pos   : CPU가 VBO에 올린 (x, y, z) 좌표를 입력으로 받음.

void main()
{
    // gl_Position: built-in output variable of type vec4 to which vertex position in clip space is assigned.
    gl_Position = vec4(vin_pos.x, vin_pos.y, vin_pos.z, 1.0);
    // gl_Position : GLSL 내장 출력 변수. 정점의 클립 공간(clip space) 좌표를 vec4로 써야 함.
    // w=1.0       : 동차 좌표(homogeneous coordinate). 원근 분할 후 NDC로 변환됨.
    //               이 예제는 변환 행렬 없이 좌표를 그대로 넘기므로, CPU에서 준 [-1,1] 범위
    //               좌표가 클립 공간에서도 동일하게 유지됨.

    // gl_Position.xyz = vin_pos;
    // gl_Position.w = 1.0;
    // (위는 동일한 결과를 내는 swizzle 표기법 예시 — 주석 처리된 대안 코드)
}
'''

# 프래그먼트 셰이더 소스 (GLSL): 삼각형 내부의 각 픽셀 색상을 결정, 픽셀마다 GPU에서 실행
g_fragment_shader_src = '''
#version 330 core

// output fragment color of type vec4.
out vec4 FragColor;
// out vec4 FragColor: 이 픽셀의 최종 색상 출력. (R, G, B, A) 각 채널 0.0~1.0 범위.

void main()
{
    // set the fragment color to white.
    FragColor = vec4(1.0f, 1.0f, 1.0f, 1.0f);
    // R=1, G=1, B=1, A=1 → 완전 불투명한 흰색.
    // 모든 삼각형 픽셀이 동일한 흰색으로 칠해짐(조명·텍스처 없음).
}
'''

# =============================================================================
# load_shaders()
# 역할: GLSL 소스 문자열을 받아 GPU에서 사용할 셰이더 프로그램 객체를 생성·반환.
#
# 내부 3단계:
#   1) 셰이더 컴파일 : 소스 → GPU가 이해하는 바이너리 (glCreateShader → glCompileShader)
#   2) 프로그램 링크 : 두 셰이더를 하나의 파이프라인으로 결합 (glLinkProgram)
#   3) 정리         : 링크 후 개별 셰이더 객체는 불필요하므로 삭제 (glDeleteShader)
# =============================================================================
def load_shaders(vertex_shader_source, fragment_shader_source):
    # build and compile our shader program
    # ------------------------------------

    # vertex shader
    vertex_shader = glCreateShader(GL_VERTEX_SHADER)    # create an empty shader object
    # glCreateShader(GL_VERTEX_SHADER): GPU 드라이버에 "버텍스 셰이더 슬롯"을 할당하고
    #                                   그 ID(정수)를 반환. 아직 소스 코드는 없음.
    glShaderSource(vertex_shader, vertex_shader_source) # provide shader source code
    # glShaderSource: 위에서 만든 셰이더 객체에 GLSL 소스 문자열을 연결.
    glCompileShader(vertex_shader)                      # compile the shader object
    # glCompileShader: GLSL 소스를 GPU 드라이버가 GPU 바이너리로 컴파일.

    # check for shader compile errors
    # 컴파일 성공 여부(GL_COMPILE_STATUS)를 조회하여 실패 시 오류 로그를 출력.
    # 오류 예: 문법 오류, 미선언 변수 사용 등.
    success = glGetShaderiv(vertex_shader, GL_COMPILE_STATUS)
    if (not success):
        infoLog = glGetShaderInfoLog(vertex_shader)
        print("ERROR::SHADER::VERTEX::COMPILATION_FAILED\n" + infoLog.decode())

    # fragment shader
    # 버텍스 셰이더와 동일한 절차로 프래그먼트 셰이더를 컴파일.
    fragment_shader = glCreateShader(GL_FRAGMENT_SHADER)    # create an empty shader object
    glShaderSource(fragment_shader, fragment_shader_source) # provide shader source code
    glCompileShader(fragment_shader)                        # compile the shader object

    # check for shader compile errors
    success = glGetShaderiv(fragment_shader, GL_COMPILE_STATUS)
    if (not success):
        infoLog = glGetShaderInfoLog(fragment_shader)
        print("ERROR::SHADER::FRAGMENT::COMPILATION_FAILED\n" + infoLog.decode())

    # link shaders
    # 두 셰이더를 하나의 "셰이더 프로그램"으로 링크.
    # 링크 결과로 완성된 렌더링 파이프라인(버텍스→프래그먼트)이 만들어짐.
    shader_program = glCreateProgram()               # create an empty program object
    glAttachShader(shader_program, vertex_shader)    # attach the shader objects to the program object
    glAttachShader(shader_program, fragment_shader)
    glLinkProgram(shader_program)                    # link the program object
    # glLinkProgram: 두 셰이더의 입출력 인터페이스(varying 변수 등)가 서로 맞는지 검증하고
    #               최종 GPU 실행 파일을 생성.

    # check for linking errors
    # 링크 성공 여부를 조회하여 실패 시 오류 로그를 출력.
    # 오류 예: vertex out ↔ fragment in 변수 이름/타입 불일치.
    success = glGetProgramiv(shader_program, GL_LINK_STATUS)
    if (not success):
        infoLog = glGetProgramInfoLog(shader_program)
        print("ERROR::SHADER::PROGRAM::LINKING_FAILED\n" + infoLog.decode())

    glDeleteShader(vertex_shader)
    glDeleteShader(fragment_shader)
    # 링크 완료 후 개별 셰이더 객체는 프로그램 안에 복사되어 있으므로
    # 더 이상 필요 없음 → GPU 메모리 해제.

    return shader_program    # return the shader program
    # 반환된 ID를 glUseProgram()에 넘겨 렌더 루프에서 활성화할 수 있음.


# =============================================================================
# key_callback()
# 역할: GLFW 키보드 이벤트 콜백. ESC 키를 누르면 창을 닫도록 플래그를 설정.
# 매개변수:
#   window   : 이벤트가 발생한 GLFW 창 핸들
#   key      : 눌린 키 코드 (GLFW_KEY_* 상수)
#   scancode : 플랫폼 종속적인 물리 키 코드 (이 예제에서는 미사용)
#   action   : GLFW_PRESS / GLFW_RELEASE / GLFW_REPEAT
#   mods     : Shift, Ctrl, Alt 등 수식키 비트마스크 (이 예제에서는 미사용)
# =============================================================================
def key_callback(window, key, scancode, action, mods):
    if key==GLFW_KEY_ESCAPE and action==GLFW_PRESS:
        glfwSetWindowShouldClose(window, GLFW_TRUE);
        # glfwSetWindowShouldClose: 창의 "닫혀야 함" 플래그를 True로 설정.
        # 다음 렌더 루프 조건 검사(glfwWindowShouldClose)에서 False가 되어 루프 탈출.

# =============================================================================
# main()
# 역할: 프로그램 진입점. 초기화 → 데이터 준비 → 렌더 루프 → 종료 순으로 진행.
# =============================================================================
def main():
    # initialize glfw
    # GLFW 라이브러리 초기화. 실패하면 창 생성 자체가 불가능하므로 즉시 종료.
    if not glfwInit():
        return
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3)   # OpenGL 3.3
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3)
    # glfwWindowHint: 다음에 생성할 창(컨텍스트)의 속성을 미리 지정하는 힌트.
    # MAJOR=3, MINOR=3 → OpenGL 3.3 컨텍스트 요청.
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE)  # Do not allow legacy OpenGl API calls
    # CORE_PROFILE: 구식(deprecated) OpenGL API(고정 파이프라인 등)를 비활성화.
    #               셰이더 기반의 현대적 OpenGL만 사용하도록 강제.
    glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GL_TRUE) # for macOS
    # FORWARD_COMPAT: 미래 버전과 호환되지 않는 기능을 금지. macOS에서 필수.

    # create a window and OpenGL context
    # 800×800 픽셀 창과 OpenGL 3.3 Core 컨텍스트를 동시에 생성.
    # 세 번째 인수: 창 제목 / 네 번째: 전체화면 모니터(None=창 모드) / 다섯 번째: 공유 컨텍스트(None)
    window = glfwCreateWindow(800, 800, '3-hello-triangle', None, None)
    if not window:
        glfwTerminate()
        return
    glfwMakeContextCurrent(window)
    # glfwMakeContextCurrent: 생성한 OpenGL 컨텍스트를 현재 스레드에 바인딩.
    # 이후 호출되는 모든 OpenGL 함수는 이 컨텍스트(=이 창의 GPU 상태)에 적용됨.

    # register event callbacks
    glfwSetKeyCallback(window, key_callback);
    # GLFW가 키보드 이벤트를 감지하면 key_callback 함수를 자동으로 호출하도록 등록.

    # load shaders
    # GLSL 소스를 컴파일·링크하여 GPU에서 실행 가능한 셰이더 프로그램을 얻음.
    shader_program = load_shaders(g_vertex_shader_src, g_fragment_shader_src)

    # prepare vertex data (in main memory)
    # 삼각형을 구성하는 3개 정점의 (x, y, z) 좌표를 CPU 메모리에 준비.
    # 좌표계: NDC(Normalized Device Coordinates), x·y 범위 [-1, 1].
    #   왼쪽 하단(-1,-1,0), 오른쪽 하단(1,-1,0), 꼭대기(0,1,0) → 화면 꽉 채우는 삼각형.
    # glm.array(glm.float32, ...): GPU에 바로 올릴 수 있는 C 호환 float32 배열 생성.
    vertices = glm.array(glm.float32,
        -1.0, -1.0, 0.0, # left vertex x, y, z coordinates
         1.0, -1.0, 0.0, # right vertex x, y, z coordinates
         0.0,  1.0, 0.0  # top vertex x, y, z coordinates
    )

    # ==========================================================================
    # VAO (Vertex Array Object)
    # 역할: VBO 바인딩 상태 + glVertexAttribPointer 설정을 통째로 기억하는 오브젝트.
    #       한 번 설정해 두면 렌더 루프에서 glBindVertexArray(VAO)만으로 전체 상태를 복원.
    # ==========================================================================
    # create and activate VAO (vertex array object)
    VAO = glGenVertexArrays(1)  # create a vertex array object ID and store it to VAO variable
    # glGenVertexArrays(1): GPU에 VAO 슬롯 1개를 할당하고 그 ID를 반환.
    glBindVertexArray(VAO)      # activate VAO
    # glBindVertexArray: VAO를 현재 활성 VAO로 바인딩.
    # 이후 VBO 바인딩과 glVertexAttribPointer 호출이 모두 이 VAO에 기록됨.

    # ==========================================================================
    # VBO (Vertex Buffer Object)
    # 역할: 정점 데이터(좌표, 색상, UV 등)를 CPU 메모리에서 GPU 메모리(VRAM)로 올리는 버퍼.
    # ==========================================================================
    # create and activate VBO (vertex buffer object)
    VBO = glGenBuffers(1)   # create a buffer object ID and store it to VBO variable
    # glGenBuffers(1): GPU에 버퍼 슬롯 1개를 할당하고 그 ID를 반환.
    glBindBuffer(GL_ARRAY_BUFFER, VBO)  # activate VBO as a vertex buffer object
    # GL_ARRAY_BUFFER 타깃에 VBO를 바인딩 → 이후 GL_ARRAY_BUFFER 관련 명령이 이 VBO에 적용.

    # copy vertex data to VBO
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices.ptr, GL_STATIC_DRAW) # allocate GPU memory for and copy vertex data to the currently bound vertex buffer
    # glBufferData: GPU 메모리를 vertices.nbytes(=9 floats × 4 bytes = 36 bytes)만큼 할당하고
    #               vertices.ptr(C 포인터)가 가리키는 데이터를 복사.
    # GL_STATIC_DRAW: 데이터를 한 번 올리고 자주 그릴 것임을 드라이버에게 힌트 → VRAM에 최적 배치.

    # configure vertex attributes
    # glVertexAttribPointer: "VBO의 데이터를 셰이더의 어떤 attribute(location)에,
    #                         어떤 형식으로 읽어줄지" 를 VAO에 기록하는 함수.
    # 인수 설명:
    #   0                       : attribute index (셰이더의 layout(location=0)과 일치)
    #   3                       : 정점 하나당 요소 수 (x, y, z → 3개)
    #   GL_FLOAT                : 각 요소의 데이터 타입
    #   GL_FALSE                : 정규화(normalize) 안 함 (이미 [-1,1] 범위)
    #   3 * glm.sizeof(glm.float32) : stride(한 정점에서 다음 정점까지의 바이트 간격) = 12 bytes
    #   None                    : offset(버퍼 시작부터 첫 정점 데이터까지의 오프셋) = 0
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * glm.sizeof(glm.float32), None)
    glEnableVertexAttribArray(0)
    # glEnableVertexAttribArray(0): index 0번 attribute를 활성화해야 셰이더가 실제로 읽을 수 있음.

    # ==========================================================================
    # 렌더 루프 (Render Loop / Game Loop)
    # 역할: 창이 닫힐 때까지 매 프레임마다 화면을 지우고 삼각형을 다시 그리는 반복.
    # 프레임 순서: Clear → Draw → SwapBuffers → PollEvents
    # ==========================================================================
    # loop until the user closes the window
    while not glfwWindowShouldClose(window):
        # render
        glClear(GL_COLOR_BUFFER_BIT)
        # GL_COLOR_BUFFER_BIT: 백 버퍼의 색상 채널을 기본값(검정)으로 초기화.
        # 매 프레임 지워야 이전 프레임 잔상 없이 깨끗하게 그릴 수 있음.

        glUseProgram(shader_program)
        # 이후의 draw call에 사용할 셰이더 프로그램을 GPU에 활성화.
        # 활성화된 프로그램이 버텍스/프래그먼트 셰이더를 결정함.
        glBindVertexArray(VAO)
        # VAO를 바인딩 → 앞서 저장해 둔 VBO 연결 + attribute 설정이 한 번에 복원됨.
        glDrawArrays(GL_TRIANGLES, 0, 3)
        # glDrawArrays: VAO에 연결된 VBO 데이터를 읽어 삼각형을 그리는 실제 draw call.
        #   GL_TRIANGLES : 정점 3개씩 묶어 삼각형 하나로 해석하는 프리미티브 타입.
        #   0            : 시작 정점 인덱스 (0번째 정점부터 읽기 시작)
        #   3            : 읽을 정점 개수 (3개 → 삼각형 1개)

        # swap front and back buffers
        glfwSwapBuffers(window)
        # 더블 버퍼링: 백 버퍼(방금 그린 결과)와 프론트 버퍼(현재 화면에 표시 중)를 교체.
        # 교체가 완료되면 방금 그린 삼각형이 화면에 나타남. 깜박임(tearing) 방지 효과.

        # poll events
        glfwPollEvents()
        # OS로부터 대기 중인 이벤트(키보드, 마우스, 창 크기 변경 등)를 수집하고
        # 등록된 콜백 함수들(key_callback 등)을 호출함.

    # terminate glfw
    glfwTerminate()
    # GLFW가 내부적으로 할당한 모든 자원(창, 컨텍스트 등)을 해제하고 라이브러리를 종료.
    # VBO·VAO·셰이더 프로그램은 컨텍스트 종료 시 GPU 드라이버가 자동으로 정리.

# =============================================================================
# 스크립트 직접 실행 시 main() 호출.
# 다른 파일에서 import 될 경우 main()이 자동 실행되지 않도록 보호.
# =============================================================================
if __name__ == "__main__":
    main()
