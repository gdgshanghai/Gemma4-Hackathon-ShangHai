#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

FOUNDATION_EXPORT NSString * const ASDGgufNativeRunnerErrorDomain;

@interface ASDGgufNativeRunner : NSObject

- (instancetype)init NS_UNAVAILABLE;

- (nullable instancetype)initWithModelPath:(NSString *)modelPath
                                mmprojPath:(NSString *)mmprojPath
                                     error:(NSError **)error NS_DESIGNATED_INITIALIZER;

/// 当前 mmproj 是否支持音频输入。纯视觉投影器为 NO，调用方应跳过音频。
@property (nonatomic, readonly) BOOL supportsAudio;

- (nullable NSString *)generateWithSystemPrompt:(NSString *)systemPrompt
                                     userPrompt:(NSString *)userPrompt
                                     mediaPaths:(NSArray<NSString *> *)mediaPaths
                                          error:(NSError **)error;

- (BOOL)beginExplanationSessionWithSystemPrompt:(NSString *)systemPrompt
                                     userPrompt:(NSString *)userPrompt
                               assistantContext:(NSString *)assistantContext
                                     mediaPaths:(NSArray<NSString *> *)mediaPaths
                                          error:(NSError **)error;

- (nullable NSString *)sendExplanationUserMessage:(NSString *)message
                                  maxOutputTokens:(NSInteger)maxOutputTokens
                                            error:(NSError **)error;

- (void)invalidateExplanationSession;

@end

NS_ASSUME_NONNULL_END
