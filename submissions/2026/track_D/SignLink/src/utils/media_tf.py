 # 使用 LSTM/Transformer 处理 MediaPipe 提取的时间序列数据
 import tensorflow as tf 
 def build_sign_model(input_shape, num_classes):
	model = tf.keras.Sequential([ 
	# 输入是 (时间帧数, 关键点特征数) 
	tf.keras.layers.LSTM(128, return_sequences=True, input_shape=input_shape), tf.keras.layers.Dropout(0.3), 
	tf.keras.layers.LSTM(64), 
	tf.keras.layers.Dense(64, activation='relu'), 
	tf.keras.layers.Dense(num_classes, activation='softmax') 
	# 输出识别的词汇概率 
	]) 
	model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy']) 
	return model 
	
	
	Flutter (移动端调用 TFLite):
	code Dart 
	// 使用 tflite_flutter 插件
	class SignRecognitionEngine { Interpreter? _interpreter;
	Future<void> loadModel() async { _interpreter = await Interpreter.fromAsset('sign_language_model.tflite'); } // 每一帧图像处理逻辑 void processFrame(List<double> handLandmarks) { // handLandmarks 是从 MediaPipe 提取的 21 个点的坐标序列 var input = prepareInput(handLandmarks); 
	var output = List.filled(1 * numClasses, 0.0).reshape([1, numClasses]);
	_interpreter!.run(input, output); 
	import tensorflow as tf 
 def build_sign_model(input_shape, num_classes):
	model = tf.keras.Sequential([ 
	# 输入是 (时间帧数, 关键点特征数) 
	tf.keras.layers.LSTM(128, return_sequences=True, input_shape=input_shape), tf.keras.layers.Dropout(0.3), 
	tf.keras.layers.LSTM(64), 
	tf.keras.layers.Dense(64, activation='relu'), 
	tf.keras.layers.Dense(num_classes, activation='softmax') 
	# 输出识别的词汇概率 
	]) 
	model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy']) 
	return model import tensorflow as tf 
 def build_sign_model(input_shape, num_classes):
	model = tf.keras.Sequential([ 
	# 输入是 (时间帧数, 关键点特征数) 
	tf.keras.layers.LSTM(128, return_sequences=True, input_shape=input_shape), tf.keras.layers.Dropout(0.3), 
	tf.keras.layers.LSTM(64), 
	tf.keras.layers.Dense(64, activation='relu'), 
	tf.keras.layers.Dense(num_classes, activation='softmax') 
	# 输出识别的词汇概率 
	]) 
	model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy']) 
	return model  获取概率最高的索引并转换为文字 String word = labelMap[getHighestProbIndex(output)]; 
	signalingService.sendRecognizedText(word); } }aist/