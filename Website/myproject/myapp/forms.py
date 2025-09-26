from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import PaymentProof, MegaVideo, MembershipUpgradeRequest
import os

class CustomUserCreationForm(UserCreationForm):
    payment_proof = forms.ImageField(
        required=True,
        help_text='Upload proof of payment (JPG, JPEG, PNG, max 2MB)',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png'})
    )
    
    agree_to_terms = forms.BooleanField(
        required=True,
        label='I agree to the Terms and Conditions',
        error_messages={'required': 'You must agree to the Terms and Conditions to register.'}
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Simplify password help text
        self.fields['password1'].help_text = 'Create a secure password.'
        # Remove password2 help text completely
        self.fields['password2'].help_text = ''

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            payment_proof = PaymentProof(
                user=user,
                image=self.cleaned_data['payment_proof']
            )
            payment_proof.save()
        return user

class MegaVideoForm(forms.ModelForm):
    class Meta:
        model = MegaVideo
        fields = ['title', 'description', 'mega_file_link', 'thumbnail', 'thumbnail_url', 'membership_tier', 'is_free']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'thumbnail': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png',
                'data-preview': '#thumbnail-preview'
            }),
            'thumbnail_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Or enter a URL to an image'
            })
        }
        help_texts = {
            'thumbnail': 'Upload a thumbnail image (max 2MB, JPG/PNG)',
            'thumbnail_url': 'Alternatively, you can provide a URL to an existing image',
            'mega_file_link': 'Enter the MEGA link for the video',
            'membership_tier': 'Select the membership tier required to access this video',
            'is_free': 'Make this video available to all users regardless of membership'
        }

    def clean(self):
        cleaned_data = super().clean()
        thumbnail = cleaned_data.get('thumbnail')
        thumbnail_url = cleaned_data.get('thumbnail_url')

        if not thumbnail and not thumbnail_url:
            raise forms.ValidationError(
                "Please either upload a thumbnail image or provide a thumbnail URL"
            )

        return cleaned_data

class PaymentProofForm(forms.ModelForm):
    """Form for uploading payment proof"""
    class Meta:
        model = PaymentProof
        fields = ['image']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }
        
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Check file size (2MB limit)
            if image.size > 2 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 2MB')
            
            # Check file type
            valid_extensions = ['.jpg', '.jpeg', '.png']
            ext = os.path.splitext(image.name)[1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError('Only JPG, JPEG, and PNG files are allowed')
                
        return image

class MembershipUpgradeRequestForm(forms.ModelForm):
    """Form for submitting membership upgrade requests"""
    class Meta:
        model = MembershipUpgradeRequest
        fields = ['reason', 'screenshot']
        widgets = {
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Please explain why you want to upgrade your membership...'
            }),
            'screenshot': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png'
            })
        }
        help_texts = {
            'reason': 'Please provide a brief explanation of why you want to upgrade your membership.',
            'screenshot': 'Upload a screenshot of your payment (JPG or PNG, max 5MB)'
        }

    def clean_screenshot(self):
        screenshot = self.cleaned_data.get('screenshot')
        if screenshot:
            # Check file size (5MB limit)
            if screenshot.size > 5 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 5MB')
            
            # Check file type
            valid_extensions = ['.jpg', '.jpeg', '.png']
            ext = os.path.splitext(screenshot.name)[1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError('Only JPG, JPEG, and PNG files are allowed')
                
        return screenshot
