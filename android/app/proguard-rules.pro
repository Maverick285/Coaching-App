# Keep kotlinx.serialization metadata.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt

# Keep generated serializers.
-keep,includedescriptorclasses class com.buddy.app.**$$serializer { *; }
-keepclassmembers class com.buddy.app.** {
    *** Companion;
}
-keepclasseswithmembers class com.buddy.app.** {
    kotlinx.serialization.KSerializer serializer(...);
}
