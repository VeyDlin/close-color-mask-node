from PIL import Image
import cv2
import numpy as np


from invokeai.app.services.image_records.image_records_common import ImageCategory, ResourceOrigin
from invokeai.app.invocations.baseinvocation import (
    BaseInvocation,
    InputField,
    invocation,
    InvocationContext,
    WithMetadata,
    WithWorkflow,
)

from invokeai.app.invocations.primitives import (
    ImageField,
    ImageOutput,
    ColorField
)


@invocation(
    "close_color_mask",
    title="Close Color Mask",
    tags=["image", "mask"],
    category="image",
    version="1.0.0",
)
class CloseColorMaskInvocation(BaseInvocation, WithMetadata, WithWorkflow):
    """Create a mask for an image based on a closely matching color"""
    image: ImageField = InputField(default=None, description="The image from which to create the mask")
    color: ColorField = InputField(description="The reference color used to create the mask")
    iterations: int = InputField(default=1, description="The number of times morphological operations will be applied")
    kernel_size: int = InputField(default=2, description="The size of the kernel for morphological operations")
    threshold: int = InputField(default=5, description="The color match threshold for mask creation")
    smooth_outline: int = InputField(default=5, description="The amount of blurring applied to the image's edges for a smoother outline")


    def invoke(self, context: InvocationContext) -> ImageOutput:
        image = context.services.images.get_pil_image(self.image.image_name)  
        cv_image = self.pil2cv2_image(image)
 
        center_color = cv2.cvtColor(
            np.uint8([[[
                self.color.b, 
                self.color.g, 
                self.color.r
            ]]]), 
            cv2.COLOR_BGR2YCrCb
        )[0][0]

        lower_color = np.uint8([
            0, 
            max(center_color[1] - self.threshold, 0), 
            max(center_color[2] - self.threshold, 0)
        ])
        upper_color = np.uint8([
            255, 
            min(center_color[1] + self.threshold, 255), 
            min(center_color[2] + self.threshold, 255)
        ])

        image_converted = cv2.cvtColor(cv_image, cv2.COLOR_BGR2YCrCb)
        mask = cv2.inRange(image_converted, lower_color, upper_color)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.kernel_size, self.kernel_size))

        mask = cv2.bitwise_not(mask)
        
        mask = cv2.dilate(mask, kernel, iterations=self.iterations)
        mask = cv2.erode(mask, kernel, iterations=self.iterations)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=self.iterations)

        smooth_outline = self.smooth_outline if self.smooth_outline % 2 == 1 else self.smooth_outline + 1
        mask = cv2.GaussianBlur(mask, (smooth_outline, smooth_outline), 0)
        
        mask = cv2.bitwise_not(mask)

        image_dto = context.services.images.create(
            image=self.cv2Pilimage(mask),
            image_origin=ResourceOrigin.INTERNAL,
            image_category=ImageCategory.GENERAL,
            node_id=self.id,
            session_id=context.graph_execution_state_id,
            is_intermediate=self.is_intermediate,
            workflow=self.workflow,
        )

        return ImageOutput(
            image=ImageField(image_name=image_dto.image_name),
            width=image_dto.width,
            height=image_dto.height,
        )
    
    def pil2cv2_image(self, image):
        numpy_image = np.array(image)
        return cv2.cvtColor(numpy_image, cv2.COLOR_RGBA2BGRA)
    

    def cv2Pilimage(self, image):
        return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA))