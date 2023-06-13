import shutil
import tempfile

from django import forms
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from ..models import Follow, Group, Post, User

TEST_OF_POST: int = 13
FIRST_NUMBER_OF_POSTS = 10
SECOND_NUMBER_OF_POSTS = 3


class TaskPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        settings.MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        super().setUpClass()
        cls.user = User.objects.create(username='NoName')
        cls.user_another = User.objects.create(username='Another_User')
        cls.post = Post.objects.create(
            author=cls.user,
            text='test_post',
            image=uploaded,
        )
        cls.group = Group.objects.create(
            title='test_title',
            slug='test_slug',
            description='test_description',
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_posts',
                    kwargs={'slug': self.group.slug}): 'posts/group_list.html',
            reverse('posts:profile',
                    kwargs={'username': f'{self.user}'}): 'posts/profile.html',
            reverse('posts:post_detail',
                    kwargs={'post_id':
                            f'{self.post.id}'}): 'posts/post_detail.html',
            reverse('posts:post_create'): 'posts/create_post.html',
        }

        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)
                response = self.authorized_client.get(reverse(
                    'posts:post_edit', kwargs={'post_id': f'{self.post.id}'}))
                self.assertTemplateUsed(response, 'posts/create_post.html')

    def exttest_post_index_group_profile_page_show_correct_cont(self):
        """Проверяем Context страницы index, group, profile"""
        context = [
            self.authorized_client.get(reverse('posts:index')),
            self.authorized_client.get(reverse(
                'posts:group_posts', kwargs={'slug': self.group.slug})),
            self.authorized_client.get(reverse(
                'posts:profile', kwargs={'username': self.author.username})),
        ]
        for response in context:
            first_object = response.context['page_obj'][0]
            context_objects = {
                self.author.id: first_object.author.id,
                self.post.text: first_object.text,
                self.group.slug: first_object.group.slug,
                self.post.id: first_object.id,
                self.post.image: first_object.image
            }
            for reverse_name, response_name in context_objects.items():
                with self.subTest(reverse_name=reverse_name):
                    self.assertEqual(response_name, reverse_name)

    def test_post_detail_page_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.id}))
        post_text_0 = {response.context['post'].text: 'Тестовый пост',
                       response.context['post'].group: self.group,
                       response.context['post'].author: self.user.username,
                       response.context['post'].image: self.user.username, }
        for value, expected in post_text_0.items():
            self.assertEqual(post_text_0[value], expected)

    def test_post_create_page_show_correct_context(self):
        """Шаблон post_create сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:post_create'))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
            'image': forms.fields.ImageField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_post_edit_page_show_correct_context(self):
        """Шаблон post_edit сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk}))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
            'image': forms.fields.ImageField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_post_added_correctly(self):
        """Пост при создании добавлен корректно"""
        post = Post.objects.create(
            text='Тестовый текст проверка как добавился',
            author=self.user,
            group=self.group)
        response_index = self.authorized_client.get(
            reverse('posts:index'))
        response_group = self.authorized_client.get(
            reverse('posts:group_posts',
                    kwargs={'slug': f'{self.group.slug}'}))
        response_profile = self.authorized_client.get(
            reverse('posts:profile',
                    kwargs={'username': f'{self.user.username}'}))
        index = response_index.context['page_obj']
        group = response_group.context['page_obj']
        profile = response_profile.context['page_obj']
        self.assertIn(post, index, 'поста нет на главной')
        self.assertIn(post, group, 'поста нет в профиле')
        self.assertIn(post, profile, 'поста нет в группе')

    def test_post_added_correctly_user(self):
        """Пост при создании не добавляется другому пользователю
           Но виден на главной и в группе"""
        group_for_another_user = Group.objects.create(
            title='Тестовая группа',
            slug='test_group_for_another_user'
        )
        posts_count = Post.objects.filter(group=self.group).count()
        post = Post.objects.create(
            text='Тестовый пост от другого автора',
            author=self.user_another,
            group=group_for_another_user)
        response_profile = self.authorized_client.get(
            reverse('posts:profile',
                    kwargs={'username': f'{self.user.username}'}))
        group = Post.objects.filter(group=self.group).count()
        profile = response_profile.context['page_obj']
        self.assertEqual(group, posts_count, 'поста нет в другой группе')
        self.assertNotIn(post, profile,
                         'поста нет в группе другого пользователя')


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='NewUser')
        cls.author = User.objects.create_user(
            username='test_name',
            email='test@mail.ru',
            password='test_pass',
        )
        cls.group = Group.objects.create(
            title=('test_title'),
            slug='test_slug2',
            description='test_description'
        )
        cls.posts = []
        for i in range(TEST_OF_POST):
            cls.posts.append(Post(
                text='test_post',
                author=cls.author,
                group=cls.group
            ))
        Post.objects.bulk_create(cls.posts)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_first_page_contains_ten_posts(self):
        list_urls = {
            reverse('posts:index'): 'posts/index.html',
            reverse(
                'posts:group_posts',
                kwargs={
                    'slug': f'{self.group.slug}'}): 'posts/group_list.html',
            reverse(
                'posts:profile',
                kwargs={
                    'username': f'{self.author}'}): 'posts/post_detail.html',
        }
        for tested_url in list_urls.keys():
            response = self.client.get(tested_url)
            self.assertEqual(len(
                response.context.get('page_obj').object_list),
                FIRST_NUMBER_OF_POSTS
            )

    def test_second_page_contains_three_posts(self):
        list_urls = {
            reverse('posts:index') + '?page=2': 'posts/index.html',
            reverse(
                'posts:group_posts',
                kwargs={'slug': f'{self.group.slug}'}) + '?page=2':
                    'posts/group_list.html',
            reverse(
                'posts:profile',
                kwargs={'username': f'{self.author}'}) + '?page=2':
                    'posts/post_detail.html',
        }
        for tested_url in list_urls.keys():
            response = self.client.get(tested_url)
            self.assertEqual(len(
                response.context.get('page_obj').object_list),
                SECOND_NUMBER_OF_POSTS
            )


class FollowTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_one = User.objects.create_user(username='user_one')
        cls.user_two = User.objects.create_user(username='user_two')
        cls.post = Post.objects.create(
            text='Тестовый текст',
            author=cls.user_two,
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user_one)

    def test_follow(self):
        """Авторизованный пользователь может подписываться на других"""
        follow_url = f'/profile/{self.user_two.username}/follow/'
        self.authorized_client.get(follow_url)
        self.assertTrue(
            Follow.objects.filter(
                user=self.user_one,
                author=self.user_two,
            ).exists())

    def test_unfollow(self):
        """Авторизованный пользователь может подписываться на других"""
        follow_url = f'/profile/{self.user_two.username}/follow/'
        unfollow_url = f'/profile/{self.user_two.username}/unfollow/'
        self.authorized_client.get(follow_url)
        self.authorized_client.get(unfollow_url)
        self.assertFalse(
            Follow.objects.filter(
                user=self.user_one,
                author=self.user_two,
            ).exists())

    def test_follow_index(self):
        follow_url = f'/profile/{self.user_two.username}/follow/'
        self.authorized_client.get(follow_url)
        response = self.authorized_client.get(reverse('posts:follow_index'))
        self.assertEqual(response.context.get('page_obj')[0], self.post)
