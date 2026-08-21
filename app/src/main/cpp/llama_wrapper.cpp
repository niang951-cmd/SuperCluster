#include <jni.h>
#include <string>

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_supercluster_InferenceEngine_loadModel(JNIEnv* env, jobject thiz,
                                                jstring modelPath, jint nCtx) {
    return 0;
}

JNIEXPORT jstring JNICALL
Java_com_supercluster_InferenceEngine_generateText(JNIEnv* env, jobject thiz,
                                                   jlong nativePtr, jstring prompt,
                                                   jint maxTokens) {
    return env->NewStringUTF("Modele non charge (compilez llama.cpp pour l'IA)");
}

JNIEXPORT void JNICALL
Java_com_supercluster_InferenceEngine_unloadModel(JNIEnv* env, jobject thiz,
                                                  jlong nativePtr) {}

JNIEXPORT jlong JNICALL
Java_com_supercluster_InferenceEngine_getModelMemoryUsage(JNIEnv* env, jobject thiz,
                                                          jlong nativePtr) {
    return 0;
}

}
