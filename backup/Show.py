import os
import traceback
import pygame
from pygame.locals import DOUBLEBUF, OPENGL

# 使用 v3 API 来加载 .model3.json
import live2d.v3 as live2d

def main():
    pygame.init()

    # 先创建 OpenGL 上下文，再初始化 live2d（glew 需要有效的 GL context）
    pygame.display.set_mode((800, 600), DOUBLEBUF | OPENGL)

    try:
        # 初始化 live2d 框架及 GL 扩展（v3 可能需要 glew）
        if hasattr(live2d, 'init'):
            live2d.init()
            print('live2d.init() called')
        if hasattr(live2d, 'glewInit'):
            try:
                live2d.glewInit()
                print('live2d.glewInit() called')
            except Exception as e:
                print('glewInit failed (non-fatal):', e)
        if hasattr(live2d, 'glInit'):
            try:
                live2d.glInit()
                print('live2d.glInit() called')
            except Exception as e:
                print('glInit failed (non-fatal):', e)

        model = live2d.LAppModel()

        model_path = os.path.join(os.path.dirname(__file__), 'hiyori_free_zh', 'hiyori_free_zh', 'runtime', 'hiyori_free_t08.model3.json')
        print('Loading model json:', model_path)
        print('Exists?', os.path.exists(model_path))

        # LoadModelJson 对模型进行初始化（可能会读取 moc/texture 等资源）
        try:
            model.LoadModelJson(model_path)
            print('Model loaded successfully')
        except Exception:
            print('Exception while loading model:')
            traceback.print_exc()

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # 清除缓冲区
            if hasattr(live2d, 'clearBuffer'):
                live2d.clearBuffer()
            # 更新并绘制模型（注意：Draw 需要有效的 GL 上下文）
            try:
                model.Update()
                model.Draw()
            except Exception:
                print('Exception during Update/Draw:')
                traceback.print_exc()

            pygame.display.flip()

    finally:
        # 尝试释放 live2d 资源
        try:
            if hasattr(live2d, 'glRelease'):
                live2d.glRelease()
            if hasattr(live2d, 'dispose'):
                live2d.dispose()
        except Exception:
            traceback.print_exc()
        pygame.quit()


if __name__ == '__main__':
    main()