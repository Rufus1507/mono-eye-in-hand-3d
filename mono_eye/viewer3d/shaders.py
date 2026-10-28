"""Mã nguồn Shader GLSL 330 Core cho PBR Rendering, Normal Mapping, Studio Lighting & Tonemapping."""
from __future__ import annotations

# 1. PBR Vertex Shader
PBR_VERTEX = """#version 330 core

layout (location = 0) in vec3 in_position;
layout (location = 1) in vec3 in_normal;
layout (location = 2) in vec2 in_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat3 u_normal_mat;

out vec3 v_world_pos;
out vec3 v_normal;
out vec2 v_uv;

void main() {
    vec4 world_pos = u_model * vec4(in_position, 1.0);
    v_world_pos = world_pos.xyz;
    v_normal = normalize(u_normal_mat * in_normal);
    v_uv = in_texcoord;
    gl_Position = u_proj * u_view * world_pos;
}
"""

# 2. PBR Fragment Shader (Cook-Torrance GGX + Screen-Space Derivative Normal Mapping)
PBR_FRAGMENT = """#version 330 core

in vec3 v_world_pos;
in vec3 v_normal;
in vec2 v_uv;

out vec4 fragColor;

uniform vec3 u_cam_pos;
uniform sampler2D u_albedo_map;
uniform sampler2D u_normal_map;
uniform sampler2D u_roughness_map;

uniform int u_has_normal_map;
uniform int u_has_rough_map;

uniform vec3 u_tint;
uniform vec2 u_uv_scale;
uniform float u_metallic;
uniform float u_roughness_factor;
uniform float u_normal_strength;

const float PI = 3.14159265359;

// Tính ma trận TBN tức thời từ đạo hàm màn hình dFdx / dFdy (có bảo vệ chống chia cho 0 khi UV thoái hóa)
mat3 cotangent_frame(vec3 N, vec3 p, vec2 uv) {
    vec3 dp1 = dFdx(p);
    vec3 dp2 = dFdy(p);
    vec2 duv1 = dFdx(uv);
    vec2 duv2 = dFdy(uv);

    float uv_len = dot(duv1, duv1) + dot(duv2, duv2);
    if (uv_len < 1e-7) {
        vec3 up = abs(N.y) < 0.999 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
        vec3 T = normalize(cross(up, N));
        vec3 B = cross(N, T);
        return mat3(T, B, N);
    }

    vec3 dp2perp = cross(dp2, N);
    vec3 dp1perp = cross(N, dp1);
    vec3 T = dp2perp * duv1.x + dp1perp * duv2.x;
    vec3 B = dp2perp * duv1.y + dp1perp * duv2.y;

    float denom = max(dot(T, T), dot(B, B));
    if (denom < 1e-7) {
        vec3 up = abs(N.y) < 0.999 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
        vec3 T = normalize(cross(up, N));
        vec3 B = cross(N, T);
        return mat3(T, B, N);
    }

    float invmax = inversesqrt(denom);
    return mat3(T * invmax, B * invmax, N);
}

// GGX / Trowbridge-Reitz NDF
float DistributionGGX(vec3 N, vec3 H, float roughness) {
    float a = roughness * roughness;
    float a2 = a * a;
    float NdotH = max(dot(N, H), 0.0);
    float NdotH2 = NdotH * NdotH;
    float denom = (NdotH2 * (a2 - 1.0) + 1.0);
    return a2 / (PI * denom * denom + 1e-5);
}

// Smith-Schlick GGX Geometry
float GeometrySchlickGGX(float NdotV, float roughness) {
    float r = (roughness + 1.0);
    float k = (r * r) / 8.0;
    return NdotV / (NdotV * (1.0 - k) + k + 1e-5);
}

float GeometrySmith(vec3 N, vec3 V, vec3 L, float roughness) {
    float NdotV = max(dot(N, V), 0.0);
    float NdotL = max(dot(N, L), 0.0);
    float ggx2 = GeometrySchlickGGX(NdotV, roughness);
    float ggx1 = GeometrySchlickGGX(NdotL, roughness);
    return ggx1 * ggx2;
}

// Schlick Fresnel
vec3 fresnelSchlick(float cosTheta, vec3 F0) {
    return F0 + (1.0 - F0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
}

void main() {
    vec2 uv = v_uv * u_uv_scale;
    vec4 albedo_sample = texture(u_albedo_map, uv);
    vec3 albedo = albedo_sample.rgb * u_tint;

    // Normal mapping
    vec3 N = normalize(v_normal);
    if (u_has_normal_map > 0) {
        vec3 map_normal = texture(u_normal_map, uv).xyz * 2.0 - 1.0;
        map_normal.xy *= u_normal_strength;
        mat3 TBN = cotangent_frame(N, -v_world_pos, uv);
        N = normalize(TBN * map_normal);
    }

    // Roughness & Metallic
    float roughness = u_roughness_factor;
    if (u_has_rough_map > 0) {
        roughness *= texture(u_roughness_map, uv).r;
    }
    roughness = clamp(roughness, 0.04, 1.0);
    float metallic = clamp(u_metallic, 0.0, 1.0);

    vec3 V = normalize(u_cam_pos - v_world_pos);
    vec3 F0 = mix(vec3(0.04), albedo, metallic);

    // Hệ thống chiếu sáng Studio 3 điểm (Key Light, Fill Light, Rim Light)
    vec3 light_dirs[3];
    vec3 light_colors[3];
    
    // 1. Key Light (Đèn chính ấm từ trên cao góc nghiêng 45 độ)
    light_dirs[0] = normalize(vec3(0.6, 1.2, 0.8));
    light_colors[0] = vec3(2.4, 2.35, 2.2);

    // 2. Fill Light (Đèn phụ dịu màu lạnh cân bằng tương phản)
    light_dirs[1] = normalize(vec3(-0.8, 0.6, -0.6));
    light_colors[1] = vec3(0.8, 0.9, 1.1);

    // 3. Rim / Top Light (Viền nổi khối)
    light_dirs[2] = normalize(vec3(0.0, 1.5, -0.9));
    light_colors[2] = vec3(0.7, 0.7, 0.75);

    vec3 Lo = vec3(0.0);
    for (int i = 0; i < 3; i++) {
        vec3 L = light_dirs[i];
        vec3 H = normalize(V + L);
        float NdotL = max(dot(N, L), 0.0);

        if (NdotL > 0.0) {
            float NDF = DistributionGGX(N, H, roughness);
            float G = GeometrySmith(N, V, L, roughness);
            vec3 F = fresnelSchlick(max(dot(H, V), 0.0), F0);

            vec3 numerator = NDF * G * F;
            float denominator = 4.0 * max(dot(N, V), 0.0) * NdotL + 0.0001;
            vec3 specular = numerator / denominator;

            vec3 kS = F;
            vec3 kD = (vec3(1.0) - kS) * (1.0 - metallic);

            Lo += (kD * albedo / PI + specular) * light_colors[i] * NdotL;
        }
    }

    // Ánh sáng môi trường Ambient Studio giả lập
    vec3 ambient_sky = vec3(0.35, 0.38, 0.42);
    vec3 ambient_ground = vec3(0.12, 0.11, 0.10);
    float up_factor = N.y * 0.5 + 0.5;
    vec3 ambient_env = mix(ambient_ground, ambient_sky, up_factor);
    vec3 ambient = ambient_env * albedo * 0.65;

    vec3 color = ambient + Lo;

    // ACES Filmic Tone Mapping
    color = (color * (2.51 * color + 0.03)) / (color * (2.43 * color + 0.59) + 0.14);
    // Gamma correction
    color = pow(color, vec3(1.0 / 2.2));

    fragColor = vec4(color, 1.0);
}
"""

# 3. Studio Background Gradient Shaders
BACKGROUND_VERTEX = """#version 330 core
layout (location = 0) in vec2 in_pos;
out vec2 v_uv;

void main() {
    v_uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.9999, 1.0);
}
"""

BACKGROUND_FRAGMENT = """#version 330 core
in vec2 v_uv;
out vec4 fragColor;

void main() {
    // Gradient studio sang trọng từ xám đậm đến xám dịu làm tôn bật mô hình 3D
    float dist = length(v_uv - vec2(0.5, 0.5));
    vec3 center_color = vec3(0.18, 0.20, 0.23);
    vec3 edge_color = vec3(0.06, 0.07, 0.08);
    vec3 color = mix(center_color, edge_color, smoothstep(0.1, 0.85, dist));
    fragColor = vec4(color, 1.0);
}
"""

ALL = [PBR_VERTEX, PBR_FRAGMENT, BACKGROUND_VERTEX, BACKGROUND_FRAGMENT]
